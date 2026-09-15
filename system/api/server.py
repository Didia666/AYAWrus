import os
import sys
import json
import uuid
import sqlite3
import hashlib
import time
import socket
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS

from system.mobile_pairing import (
    generate_pairing_payload,
    validate_pairing_token,
    consume_pairing_token,
    create_mobile_session,
    get_session_for_token,
    refresh_session,
    revoke_session,
    revoke_all_sessions,
    list_active_sessions,
    mobile_status_payload,
    qr_payload,
    SESSION_TTL_SECONDS,
    SYSTEM_ID,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from system.config import (
    LOG_FILE, QUARANTINE_DIR, QUARANTINE_INDEX_FILE, CONFIG_FILE
)
from system.quarantines.quarantine import quarantine_file, is_quarantined, _load_quarantine_index
from system.history.logs import load_log, add_log_entry

try:
    from google.oauth2 import service_account
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

try:
    import jwt
    _PYJWT_AVAILABLE = True
except ImportError:
    _PYJWT_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "scan_results.db")
FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY", "")
FCM_LEGACY_SEND_URL = "https://fcm.googleapis.com/fcm/send"
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "5001"))

FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
FCM_TOKEN_URI = "https://oauth2.googleapis.com/token"
_fcm_v1_credentials = None
_fcm_sa_info = None
_fcm_v1_token = None
_fcm_v1_token_expiry = 0
_fcm_lock = threading.Lock()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

_db_lock = threading.Lock()

_alert_bus_lock = threading.Lock()
_alert_bus_subscribers = []
_latest_alert = None


def _broadcast_alert(alert):
    global _latest_alert
    with _alert_bus_lock:
        _latest_alert = alert
        dead = []
        for q in _alert_bus_subscribers:
            try:
                q.put_nowait(alert)
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _alert_bus_subscribers.remove(q)
            except Exception:
                pass


def _get_active_local_ip():
    candidates = []
    try:
        addrs = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_DGRAM)
        for item in addrs:
            ip = item[4][0]
            if ip and ip != "127.0.0.1":
                candidates.append(ip)
    except Exception:
        pass
    try:
        for intf in socket.if_nameindex():
            name = intf[1]
            if not name or name.startswith("lo"):
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip = s.getsockname()[0]
                    if ip and ip != "127.0.0.1":
                        candidates.append(ip)
            except Exception:
                pass
    except Exception:
        pass
    seen = set()
    ordered = []
    for ip in candidates:
        if ip not in seen:
            seen.add(ip)
            ordered.append(ip)
    for ip in ordered:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return ordered[0] if ordered else "127.0.0.1"


def _require_mobile_session(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return jsonify({"success": False, "error": "Unauthorized", "message": "Missing or invalid mobile session token"}), 401
        token = auth_header.split(" ", 1)[1].strip()
        session = get_session_for_token(token)
        if not session:
            return jsonify({"success": False, "error": "Session expired", "message": "AYAWrus session expired or was revoked"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def _subscribe_alert_bus():
    import queue
    q = queue.Queue(maxsize=32)
    with _alert_bus_lock:
        _alert_bus_subscribers.append(q)
        snapshot = _latest_alert
    return q, snapshot


def load_app_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_app_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception:
        return False


def get_fcm_project_id():
    cfg = load_app_config()
    env_pid = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    if env_pid:
        return env_pid
    return cfg.get("firebase_project_id", "").strip()


def get_fcm_service_account_path():
    cfg = load_app_config()
    env_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if env_path:
        return env_path
    raw = cfg.get("firebase_service_account", "").strip()
    if not raw:
        return ""
    if os.path.isabs(raw):
        return raw
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), raw)


def _fcm_v1_send_url():
    pid = get_fcm_project_id()
    if not pid:
        return None
    return f"https://fcm.googleapis.com/v1/projects/{pid}/messages:send"


def _load_service_account_info():
    global _fcm_sa_info
    if _fcm_sa_info is not None:
        return _fcm_sa_info
    sa_path = get_fcm_service_account_path()
    if not sa_path or not os.path.exists(sa_path):
        return None
    try:
        with open(sa_path, "r") as f:
            _fcm_sa_info = json.load(f)
        return _fcm_sa_info
    except Exception:
        return None


def _fcm_v1_token_via_google_auth(now: int):
    global _fcm_v1_credentials
    sa_path = get_fcm_service_account_path()
    if not sa_path or not os.path.exists(sa_path):
        return None
    try:
        _fcm_v1_credentials = service_account.Credentials.from_service_account_file(
            sa_path, scopes=FCM_SCOPES
        )
        try:
            from google.auth.transport.requests import Request
            _fcm_v1_credentials.refresh(Request())
        except Exception:
            _fcm_v1_credentials.refresh(None)
        token = _fcm_v1_credentials.token
        expiry_seconds = getattr(_fcm_v1_credentials, "expiry", None)
        if expiry_seconds:
            try:
                exp = int(expiry_seconds.timestamp())
            except Exception:
                exp = now + 3500
        else:
            exp = now + 3500
        return token, exp
    except Exception as e:
        print(f"[FCM] google-auth token failed: {e}")
        return None


def _fcm_v1_token_via_pyjwt(now: int):
    sa_info = _load_service_account_info()
    if not sa_info:
        return None
    try:
        client_email = sa_info.get("client_email", "")
        private_key = sa_info.get("private_key", "")
        private_key_id = sa_info.get("private_key_id", "")
        if not client_email or not private_key:
            print("[FCM] Service account JSON missing client_email or private_key")
            return None

        issued = int(now)
        expires = issued + 3600
        scope_str = " ".join(FCM_SCOPES)

        payload = {
            "iss": client_email,
            "scope": scope_str,
            "aud": FCM_TOKEN_URI,
            "iat": issued,
            "exp": expires,
        }
        headers = {}
        if private_key_id:
            headers["kid"] = private_key_id

        assertion = jwt.encode(
            payload, private_key, algorithm="RS256", headers=headers
        )
        if isinstance(assertion, bytes):
            assertion = assertion.decode("utf-8")

        token_resp = requests.post(
            FCM_TOKEN_URI,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=10,
        )
        if token_resp.status_code != 200:
            print(f"[FCM] Token exchange failed: HTTP {token_resp.status_code} - {token_resp.text}")
            return None
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return None
        expires_in = int(token_data.get("expires_in", 3500))
        return access_token, issued + expires_in
    except Exception as e:
        print(f"[FCM] PyJWT token failed: {e}")
        return None


def _fcm_v1_get_access_token():
    global _fcm_v1_token, _fcm_v1_token_expiry
    with _fcm_lock:
        now = time.time()
        if _fcm_v1_token and _fcm_v1_token_expiry > now + 60:
            return _fcm_v1_token

        result = None
        if _GOOGLE_AUTH_AVAILABLE:
            result = _fcm_v1_token_via_google_auth(int(now))
        if result is None and _PYJWT_AVAILABLE:
            result = _fcm_v1_token_via_pyjwt(int(now))
        if result is None:
            if not _GOOGLE_AUTH_AVAILABLE and not _PYJWT_AVAILABLE:
                print("[FCM] Neither google-auth nor PyJWT installed. Install one:")
                print("      pip install google-auth  OR  pip install PyJWT cryptography")
            return None

        _fcm_v1_token, _fcm_v1_token_expiry = result
        return _fcm_v1_token


def _send_fcm_v1(file_name: str, threat_level: int) -> bool:
    pid = get_fcm_project_id()
    if not pid:
        print("[FCM] firebase_project_id not configured (set in config.json or FIREBASE_PROJECT_ID env)")
        return False

    sa_path = get_fcm_service_account_path()
    if not sa_path or not os.path.exists(sa_path):
        print(f"[FCM] Service account JSON not configured or missing: {sa_path}")
        return False

    url = _fcm_v1_send_url()
    if not url:
        return False

    token = _fcm_v1_get_access_token()
    if not token:
        return False

    body = (
        f"Malicious file '{file_name}' was found with a threat level of {threat_level}."
        if threat_level >= 70
        else f"Suspicious file '{file_name}' was detected with a threat level of {threat_level}."
    )
    title = "Malware Detected!" if threat_level >= 70 else "Suspicious File Found!"

    payload = {
        "message": {
            "topic": "malware_alerts",
            "notification": {
                "title": title,
                "body": body
            },
            "android": {
                "notification": {
                    "channel_id": "malware_alerts",
                    "click_action": "FLUTTER_NOTIFICATION_CLICK"
                },
                "priority": "HIGH"
            },
            "apns": {
                "headers": {
                    "apns-priority": "10"
                },
                "payload": {
                    "aps": {
                        "contentAvailable": True
                    }
                }
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; UTF-8"
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            print(f"[FCM v1] Notification sent for {file_name}")
            return True
        else:
            print(f"[FCM v1] Failed to send: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"[FCM v1] Error sending notification: {e}")
        return False


def _send_fcm_legacy(file_name: str, threat_level: int) -> bool:
    if not FCM_SERVER_KEY:
        print("[FCM Legacy] FCM_SERVER_KEY not configured, skipping notification")
        return False

    body = (
        f"Malicious file '{file_name}' was found with a threat level of {threat_level}."
        if threat_level >= 70
        else f"Suspicious file '{file_name}' was detected with a threat level of {threat_level}."
    )
    title = "Malware Detected!" if threat_level >= 70 else "Suspicious File Found!"

    payload = {
        "to": "/topics/malware_alerts",
        "notification": {
            "title": title,
            "body": body
        },
        "priority": "high"
    }
    headers = {
        "Authorization": f"key={FCM_SERVER_KEY}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(FCM_LEGACY_SEND_URL, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            print(f"[FCM Legacy] Notification sent for {file_name}")
            return True
        else:
            print(f"[FCM Legacy] Failed to send: HTTP {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"[FCM Legacy] Error sending notification: {e}")
        return False


def send_fcm_notification(file_name: str, threat_level: int):
    ok_v1 = _send_fcm_v1(file_name, threat_level)
    if ok_v1:
        return True
    ok_legacy = _send_fcm_legacy(file_name, threat_level)
    if ok_legacy:
        return True
    print("[FCM] No FCM backend configured. Set either:")
    print("      • HTTP v1: config.json firebase_project_id + firebase_service_account path")
    print("      • Legacy:  env var FCM_SERVER_KEY")
    return False


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_results (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            verdict TEXT NOT NULL,
            threat_level INTEGER NOT NULL,
            date_scanned TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            details TEXT,
            created_at INTEGER NOT NULL,
            batch_id TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON scan_results(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON scan_results(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON scan_results(file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON scan_results(batch_id)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_batches (
            id TEXT PRIMARY KEY,
            scan_type TEXT NOT NULL DEFAULT 'custom',
            target TEXT,
            started_at_ms INTEGER NOT NULL,
            started_at TEXT,
            completed_at_ms INTEGER,
            completed_at TEXT,
            elapsed_ms INTEGER NOT NULL DEFAULT 0,
            total_files INTEGER NOT NULL DEFAULT 0,
            clean_count INTEGER NOT NULL DEFAULT 0,
            threat_count INTEGER NOT NULL DEFAULT 0,
            suspicious_count INTEGER NOT NULL DEFAULT 0,
            malicious_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'COMPLETED',
            created_at INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_started ON scan_batches(started_at_ms)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_status ON scan_batches(status)")
    conn.commit()
    conn.close()


def generate_id(file_path: str, timestamp_ms: int) -> str:
    raw = f"{file_path}_{timestamp_ms}"
    hash_obj = hashlib.sha256(raw.encode("utf-8"))
    return hash_obj.hexdigest()[:16]


def map_verdict(result_str: str) -> str:
    if not result_str:
        return "Clean"
    upper = result_str.upper().strip()
    if upper == "MALICIOUS":
        return "Malicious"
    elif upper == "SUSPICIOUS":
        return "Suspicious"
    elif upper in ("CLEAN", "SAFE", "BENIGN"):
        return "Clean"
    else:
        return "Clean"


def calc_threat_level(result_str: str, probability) -> int:
    if probability is not None:
        try:
            p = float(probability)
            if p < 0:
                p = 0.0
            if p > 1:
                p = 1.0
            return int(round(p * 100))
        except (ValueError, TypeError):
            pass
    upper = result_str.upper().strip() if result_str else ""
    if upper == "MALICIOUS":
        return 90
    elif upper == "SUSPICIOUS":
        return 55
    else:
        return 10


def parse_timestamp(ts_str: str):
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        date_scanned = dt.strftime("%Y-%m-%d")
        timestamp_ms = int(dt.timestamp() * 1000)
        return date_scanned, timestamp_ms
    except (ValueError, TypeError):
        now = datetime.now()
        return now.strftime("%Y-%m-%d"), int(now.timestamp() * 1000)


def row_to_batch(row) -> dict:
    return {
        "id": row["id"],
        "scanType": row["scan_type"],
        "target": row["target"],
        "startedAt": row["started_at"],
        "startedAtMs": row["started_at_ms"],
        "completedAt": row["completed_at"],
        "completedAtMs": row["completed_at_ms"],
        "elapsedMs": row["elapsed_ms"],
        "totalFiles": row["total_files"],
        "cleanCount": row["clean_count"],
        "threatCount": row["threat_count"],
        "suspiciousCount": row["suspicious_count"],
        "maliciousCount": row["malicious_count"],
        "errorCount": row["error_count"],
        "status": row["status"],
    }


def row_to_scan_result(row) -> dict:
    return {
        "id": row["id"],
        "fileName": row["file_name"],
        "verdict": row["verdict"],
        "threatLevel": row["threat_level"],
        "dateScanned": row["date_scanned"],
        "timestamp": row["timestamp"],
        "status": row["status"],
        "batchId": row["batch_id"] if "batch_id" in row.keys() else None,
    }


@app.route("/api/batches", methods=["GET"])
def list_batches_endpoint():
    try:
        try:
            days_param = request.args.get("days", "30")
            limit_param = request.args.get("limit", "50")
            try:
                days = int(days_param)
            except (ValueError, TypeError):
                days = 30
            try:
                limit = int(limit_param)
            except (ValueError, TypeError):
                limit = 50
            if days < 1:
                days = 1
            if days > 365:
                days = 365
            if limit < 1:
                limit = 1
            if limit > 500:
                limit = 500
        except Exception:
            days = 30
            limit = 50

        sync_history_json_to_db()

        cutoff_ms = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM scan_batches
            WHERE started_at_ms >= ?
            ORDER BY started_at_ms DESC
            LIMIT ?
        """, (cutoff_ms, limit))
        rows = cursor.fetchall()
        batches = [row_to_batch(r) for r in rows]
        resp = jsonify(batches)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp, 200
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route("/api/batches/<batch_id>/files", methods=["GET"])
def batch_files_endpoint(batch_id):
    if not batch_id or not str(batch_id).strip():
        return jsonify({"error": "Missing batch id"}), 400
    try:
        sync_history_json_to_db()
        db = get_db()
        cursor = db.cursor()

        batch_row = None
        try:
            cursor.execute("SELECT * FROM scan_batches WHERE id = ?", (batch_id,))
            batch_row = cursor.fetchone()
        except Exception:
            pass

        cursor.execute("""
            SELECT * FROM scan_results
            WHERE batch_id = ?
            ORDER BY timestamp DESC
        """, (batch_id,))
        rows = cursor.fetchall()

        if not rows and batch_row is None:
            from system.history.batches import get_batch as _get_json_batch
            jb = None
            try:
                jb = _get_json_batch(batch_id)
            except Exception:
                jb = None
            if jb is None:
                return jsonify({"error": "Batch not found", "id": batch_id}), 404

        files = [row_to_scan_result(r) for r in rows]
        out = {
            "id": batch_id,
            "batch": row_to_batch(batch_row) if batch_row else (dict(
                id=batch_row["id"] if batch_row else batch_id,
                scanType=batch_row["scan_type"] if batch_row else "unknown",
                target=batch_row["target"] if batch_row else "",
                startedAt=batch_row["started_at"] if batch_row else "",
                startedAtMs=batch_row["started_at_ms"] if batch_row else 0,
                completedAt=batch_row["completed_at"] if batch_row else "",
                completedAtMs=batch_row["completed_at_ms"] if batch_row else 0,
                elapsedMs=batch_row["elapsed_ms"] if batch_row else 0,
                totalFiles=batch_row["total_files"] if batch_row else len(files),
                cleanCount=batch_row["clean_count"] if batch_row else 0,
                threatCount=batch_row["threat_count"] if batch_row else 0,
                suspiciousCount=batch_row["suspicious_count"] if batch_row else 0,
                maliciousCount=batch_row["malicious_count"] if batch_row else 0,
                errorCount=batch_row["error_count"] if batch_row else 0,
                status=batch_row["status"] if batch_row else "COMPLETED",
            )),
            "files": files,
            "total": len(files),
        }
        resp = jsonify(out)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp, 200
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


def sync_history_json_to_db():
    with _db_lock:
        try:
            from system.history.batches import list_batches as _list_json_batches
        except Exception:
            _list_json_batches = None

        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            if _list_json_batches is not None:
                try:
                    json_batches = _list_json_batches() or []
                    for b in json_batches:
                        bid = b.get("id")
                        if not bid:
                            continue
                        cursor.execute("SELECT id FROM scan_batches WHERE id = ?", (bid,))
                        if cursor.fetchone():
                            continue
                        cursor.execute("""
                                INSERT INTO scan_batches (id, scan_type, target, started_at_ms, started_at,
                                    completed_at_ms, completed_at, elapsed_ms, total_files, clean_count,
                                    threat_count, suspicious_count, malicious_count, error_count, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                bid,
                                (b.get("scan_type") or "custom").lower() if b.get("scan_type") else "custom",
                                b.get("target") or "",
                                int(b.get("started_at_ms") or 0),
                                b.get("started_at") or "",
                                int(b.get("completed_at_ms") or 0) if b.get("completed_at_ms") else None,
                                b.get("completed_at") or "",
                                int(b.get("elapsed_ms") or 0),
                                int(b.get("total_files") or 0),
                                int(b.get("clean_count") or 0),
                                int(b.get("threat_count") or 0),
                                int(b.get("suspicious_count") or 0),
                                int(b.get("malicious_count") or 0),
                                int(b.get("error_count") or 0),
                                (b.get("status") or "COMPLETED").upper(),
                                int(datetime.now().timestamp() * 1000),
                            ))
                    conn.commit()
                except Exception as b_err:
                    print(f"[sync: scan_batches sync failed: {b_err}")

            history = load_log()
            quarantine_paths = set()
            try:
                q_idx = _load_quarantine_index()
                for entry in q_idx:
                    op = entry.get("original_path", "")
                    if op:
                        quarantine_paths.add(op)
            except Exception:
                pass

            inserted_count = 0
            for entry in history:
                file_path = entry.get("file_path", "")
                if not file_path:
                    continue
                ts_str = entry.get("timestamp", "")
                date_scanned, timestamp_ms = parse_timestamp(ts_str)
                scan_id = generate_id(file_path, timestamp_ms)
                cursor.execute("SELECT id, batch_id FROM scan_results WHERE id = ?", (scan_id,))
                existing = cursor.fetchone()
                file_name = os.path.basename(file_path)
                result = entry.get("result", "CLEAN")
                verdict = map_verdict(result)
                threat_level = calc_threat_level(result, entry.get("probability"))
                status = "QUARANTINED" if file_path in quarantine_paths else "ACTIVE"
                details = entry.get("details", "")
                details_json = json.dumps(details) if isinstance(details, (dict, list)) else (details or "")
                batch_id = entry.get("batch_id")
                if existing:
                    if not existing["batch_id"] and batch_id:
                        try:
                            cursor.execute("UPDATE scan_results SET batch_id = ?, status = ? WHERE id = ?",
                                           (batch_id, status, scan_id))
                        except Exception:
                            pass
                    continue
                cursor.execute("""
                    INSERT INTO scan_results (id, file_name, file_path, verdict, threat_level,
                        date_scanned, timestamp, status, details, created_at, batch_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (scan_id, file_name, file_path, verdict, threat_level,
                      date_scanned, timestamp_ms, status, details_json,
                      int(datetime.now().timestamp() * 1000), batch_id))
                inserted_count += 1
            conn.commit()
            return inserted_count
        finally:
            conn.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "timestamp": int(datetime.now().timestamp() * 1000)})


def _mobile_apk_path():
    return os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "AYAWRusMobile", "app", "build", "outputs", "apk", "debug", "app-debug.apk"
    ))


@app.route("/mobile/download", methods=["GET"])
def download_mobile_apk():
    apk_path = _mobile_apk_path()
    if not os.path.isfile(apk_path):
        return jsonify({"success": False, "message": "AYAWrus Mobile APK has not been built yet"}), 404
    return send_file(apk_path, as_attachment=True, download_name="AYAWrus-Mobile.apk", mimetype="application/vnd.android.package-archive")


@app.route("/mobile/setup", methods=["GET"])
@app.route("/api/mobile/setup", methods=["GET"])
def mobile_setup_page():
    token = request.args.get("pairing_token", "")
    port = request.args.get("port", SERVER_PORT)
    system_id = request.args.get("system_id", SYSTEM_ID)
    if not token:
        return "Missing pairing token", 400
    return f"""<!doctype html>
<html><head><meta name=viewport content='width=device-width,initial-scale=1'><title>AYAWrus Mobile</title></head>
<body><h1>AYAWrus Mobile</h1><p>System: {system_id}</p><p>Server: {request.host.split(':')[0]}:{port}</p>
<p><a href='/mobile/download'>Download AYAWrus Mobile APK</a></p>
<p>After installing, open AYAWrus Mobile and scan this QR code again to pair.</p></body></html>""", 200


@app.route("/api/mobile/pair", methods=["POST"])
def pair_mobile_device():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        token = (payload.get("pairing_token") or "").strip()
        device_name = (payload.get("device_name") or "AYAWrus Mobile").strip() or "AYAWrus Mobile"
        device_id = (payload.get("device_id") or uuid.uuid4().hex).strip() or uuid.uuid4().hex

        if not token:
            return jsonify({"success": False, "error": "Invalid pairing code", "message": "Missing pairing token"}), 400

        valid = validate_pairing_token(token)
        if not valid:
            return jsonify({"success": False, "error": "Invalid pairing code", "message": "Pairing code expired, already used, or invalid"}), 401

        consumed = consume_pairing_token(token)
        if not consumed:
            return jsonify({"success": False, "error": "Pairing code already used", "message": "This QR code has already been consumed"}), 409

        session = create_mobile_session(device_name=device_name, device_id=device_id)
        if not session:
            return jsonify({"success": False, "error": "Unable to create session", "message": "AYAWrus rejected the connection"}), 500

        return jsonify({
            "success": True,
            "system_id": session["system_id"],
            "access_token": session["access_token"],
            "expires_in": int(SESSION_TTL_SECONDS),
            "message": "Mobile session created",
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": "Server error", "message": str(exc)}), 500


@app.route("/api/mobile/status", methods=["GET"])
def mobile_status():
    return jsonify(mobile_status_payload()), 200


@app.route("/api/mobile/session/refresh", methods=["POST"])
@_require_mobile_session
def refresh_mobile_session():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else ""
    session = refresh_session(token)
    if not session:
        return jsonify({"success": False, "error": "Session expired", "message": "AYAWrus session expired or was revoked"}), 401
    return jsonify({
        "success": True,
        "system_id": session["system_id"],
        "access_token": session["access_token"],
        "expires_in": int(SESSION_TTL_SECONDS),
        "message": "Session refreshed",
    }), 200


@app.route("/api/mobile/disconnect", methods=["POST"])
@_require_mobile_session
def disconnect_mobile_session():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else ""
    if token:
        revoke_session(token)
    return jsonify({"success": True, "message": "Mobile session revoked"}), 200


@app.route("/api/mobile/qr", methods=["GET"])
def mobile_qr_payload_endpoint():
    host = request.args.get("host") or _get_active_local_ip()
    port = request.args.get("port", SERVER_PORT)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = SERVER_PORT
    payload = qr_payload(host=host, port=port)
    return jsonify({"qr_payload": payload, "system_id": SYSTEM_ID, "host": host, "port": port}), 200


@app.route("/api/history", methods=["GET"])
def get_history():
    try:
        days_param = request.args.get("days", "15")
        try:
            days = int(days_param)
        except (ValueError, TypeError):
            days = 15
        if days < 1:
            days = 1
        if days > 365:
            days = 365

        sync_history_json_to_db()

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_ms = int(cutoff.timestamp() * 1000)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM scan_results
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        """, (cutoff_ms,))
        rows = cursor.fetchall()

        results = [row_to_scan_result(r) for r in rows]
        response = jsonify(results)
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        return response, 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route("/api/quarantine/<scan_id>", methods=["POST"])
@_require_mobile_session
def quarantine_by_id(scan_id):
    if not scan_id or not scan_id.strip():
        return jsonify({"error": "Missing scan ID"}), 400

    try:
        sync_history_json_to_db()
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM scan_results WHERE id = ?", (scan_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Scan result not found", "id": scan_id}), 404

        file_path = row["file_path"]
        current_status = row["status"]

        if current_status == "QUARANTINED":
            return jsonify({
                "message": "File already quarantined",
                "id": scan_id,
                "fileName": row["file_name"],
                "status": "QUARANTINED"
            }), 200

        if not os.path.exists(file_path) and not is_quarantined(file_path):
            pass

        q_result = quarantine_file(file_path)

        if "ALREADY IN QUARANTINE" in q_result or "MOVED TO QUARANTINE" in q_result or "Failed" not in q_result:
            cursor.execute("UPDATE scan_results SET status = 'QUARANTINED' WHERE id = ?", (scan_id,))
            db.commit()
            return jsonify({
                "message": "Quarantine successful",
                "id": scan_id,
                "fileName": row["file_name"],
                "status": "QUARANTINED",
                "detail": q_result
            }), 200
        else:
            return jsonify({
                "error": "Quarantine failed",
                "id": scan_id,
                "fileName": row["file_name"],
                "detail": q_result
            }), 500

    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


def notify_new_malware(file_name: str, threat_level: int):
    title = "Malware Detected!" if threat_level >= 70 else "Suspicious File Found!"
    body = (
        f"Malicious file '{file_name}' was found with a threat level of {threat_level}."
        if threat_level >= 70
        else f"Suspicious file '{file_name}' was detected with a threat level of {threat_level}."
    )
    alert_payload = {
        "fileName": file_name,
        "threatLevel": threat_level,
        "title": title,
        "body": body,
        "timestamp": int(datetime.now().timestamp() * 1000),
    }
    _broadcast_alert(alert_payload)
    t = threading.Thread(target=send_fcm_notification, args=(file_name, threat_level), daemon=True)
    t.start()


@app.route("/api/scan/notify", methods=["POST"])
def notify_scan_result():
    try:
        data = request.get_json(force=True, silent=True) or {}
        file_name = data.get("fileName") or data.get("file_name") or "unknown.exe"
        threat_level = data.get("threatLevel") or data.get("threat_level") or 50
        try:
            threat_level = int(threat_level)
        except (ValueError, TypeError):
            threat_level = 50
        if threat_level >= 50:
            notify_new_malware(file_name, threat_level)
            return jsonify({"status": "notification_triggered"}), 200
        else:
            return jsonify({"status": "skipped_low_threat"}), 200
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route("/api/alerts/latest", methods=["GET"])
def get_latest_alert():
    with _alert_bus_lock:
        latest = _latest_alert
    if latest is None:
        return jsonify({"alert": None}), 200
    return jsonify({"alert": latest}), 200


@app.route("/api/alerts/stream", methods=["GET"])
def alerts_stream():
    import queue
    q, snapshot = _subscribe_alert_bus()
    def event_generator():
        try:
            if snapshot is not None:
                yield f"data: {json.dumps(snapshot)}\n\n"
            while True:
                try:
                    item = q.get(timeout=25)
                    yield f"data: {json.dumps(item)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            pass
        finally:
            with _alert_bus_lock:
                try:
                    _alert_bus_subscribers.remove(q)
                except Exception:
                    pass
    from flask import Response
    resp = Response(event_generator(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


def create_app():
    init_db()
    sync_history_json_to_db()
    return app


def run_server():
    init_db()
    sync_history_json_to_db()
    print(f"=" * 60)
    print(f"  AYAWrus Malware Detection API Server")
    print(f"=" * 60)
    print(f"  Host: {SERVER_HOST}")
    print(f"  Port: {SERVER_PORT}")
    print(f"  DB:   {DB_FILE}")
    print(f"  CORS: Enabled")
    print(f"")
    print(f"  Endpoints:")
    print(f"    GET  /api/health")
    print(f"    GET  /api/batches?days=N&limit=N")
    print(f"    GET  /api/batches/{{id}}/files")
    print(f"    GET  /api/history?days=N")
    print(f"    POST /api/mobile/pair")
    print(f"    GET  /api/mobile/status")
    print(f"    POST /api/mobile/session/refresh")
    print(f"    POST /api/mobile/disconnect")
    print(f"    POST /api/quarantine/{{id}}")
    print(f"    POST /api/scan/notify")
    print(f"    GET  /api/alerts/latest")
    print(f"    GET  /api/alerts/stream  (SSE)")
    print(f"=" * 60)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
