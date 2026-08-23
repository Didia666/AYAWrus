import os
import sys
import json
import uuid
import sqlite3
import hashlib
import time
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from flask_cors import CORS

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
SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))

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
            created_at INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON scan_results(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON scan_results(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON scan_results(file_path)")
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


def row_to_scan_result(row) -> dict:
    return {
        "id": row["id"],
        "fileName": row["file_name"],
        "verdict": row["verdict"],
        "threatLevel": row["threat_level"],
        "dateScanned": row["date_scanned"],
        "timestamp": row["timestamp"],
        "status": row["status"]
    }


def sync_history_json_to_db():
    with _db_lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
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
                cursor.execute("SELECT id FROM scan_results WHERE id = ?", (scan_id,))
                if cursor.fetchone():
                    continue
                file_name = os.path.basename(file_path)
                result = entry.get("result", "CLEAN")
                verdict = map_verdict(result)
                threat_level = calc_threat_level(result, entry.get("probability"))
                status = "QUARANTINED" if file_path in quarantine_paths else "ACTIVE"
                details = entry.get("details", "")
                details_json = json.dumps(details) if isinstance(details, (dict, list)) else (details or "")
                cursor.execute("""
                    INSERT INTO scan_results (id, file_name, file_path, verdict, threat_level,
                        date_scanned, timestamp, status, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (scan_id, file_name, file_path, verdict, threat_level,
                      date_scanned, timestamp_ms, status, details_json, int(datetime.now().timestamp() * 1000)))
                inserted_count += 1
            conn.commit()
            return inserted_count
        finally:
            conn.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "timestamp": int(datetime.now().timestamp() * 1000)})


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
    print(f"    GET  /api/history?days=N")
    print(f"    POST /api/quarantine/{{id}}")
    print(f"    POST /api/scan/notify")
    print(f"    GET  /api/alerts/latest")
    print(f"    GET  /api/alerts/stream  (SSE)")
    print(f"=" * 60)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
