import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


PAIRING_TTL_SECONDS = 300
SESSION_TTL_SECONDS = 1800
SYSTEM_ID = os.environ.get("AYAWRUS_SYSTEM_ID") or f"AYA-{uuid.uuid4().hex[:8].upper()}"

_pairing_lock = threading.Lock()
_pairing_tokens: Dict[str, Dict[str, Any]] = {}
_mobile_sessions: Dict[str, Dict[str, Any]] = {}
_mobile_sessions_by_system: Dict[str, Dict[str, Any]] = {}


def utc_now():
    return datetime.now(timezone.utc)


def _expires_at(seconds: int):
    return (utc_now() + timedelta(seconds=seconds)).isoformat()


def _clean_expired_tokens():
    now = datetime.now(timezone.utc).timestamp()
    expired_pairings = []
    expired_sessions = []

    with _pairing_lock:
        for token, payload in list(_pairing_tokens.items()):
            if payload.get("expires_at_ts", 0) <= now:
                expired_pairings.append(token)
        for token in expired_pairings:
            _pairing_tokens.pop(token, None)

        for token, payload in list(_mobile_sessions.items()):
            if payload.get("expires_at_ts", 0) <= now:
                expired_sessions.append(token)
        for token in expired_sessions:
            _mobile_sessions.pop(token, None)
            system_id = payload.get("system_id")
            if system_id and system_id in _mobile_sessions_by_system:
                _mobile_sessions_by_system.pop(system_id, None)


def generate_pairing_payload(host: str, port: int = 5000, expires_in_seconds: int = PAIRING_TTL_SECONDS, apk_url: str = ""):
    _clean_expired_tokens()
    token = secrets.token_urlsafe(32)
    expires_dt = utc_now() + timedelta(seconds=expires_in_seconds)
    payload = {
        "protocol": "ayawrus",
        "version": 1,
        "host": host,
        "port": port,
        "pairing_token": token,
        "expires_at": expires_dt.isoformat(),
        "expires_at_ts": expires_dt.timestamp(),
        "system_id": SYSTEM_ID,
        "used": False,
        "created_at": utc_now().isoformat(),
    }
    if apk_url:
        payload["apk_url"] = apk_url
    with _pairing_lock:
        _pairing_tokens[token] = payload
    return payload


def get_active_pairing_tokens():
    _clean_expired_tokens()
    with _pairing_lock:
        return {
            token: {
                "host": payload.get("host"),
                "port": payload.get("port"),
                "expires_at": payload.get("expires_at"),
                "system_id": payload.get("system_id"),
                "used": payload.get("used", False),
            }
            for token, payload in _pairing_tokens.items()
        }


def validate_pairing_token(token: str) -> Optional[Dict[str, Any]]:
    _clean_expired_tokens()
    with _pairing_lock:
        payload = _pairing_tokens.get(token)
        if not payload:
            return None
        if payload.get("used"):
            return None
        if payload.get("expires_at_ts", 0) <= time.time():
            _pairing_tokens.pop(token, None)
            return None
        return payload


def consume_pairing_token(token: str) -> Optional[Dict[str, Any]]:
    payload = validate_pairing_token(token)
    if not payload:
        return None
    with _pairing_lock:
        entry = _pairing_tokens.get(token)
        if not entry:
            return None
        entry["used"] = True
        entry["used_at"] = utc_now().isoformat()
    return payload


def create_mobile_session(device_name: Optional[str] = None, device_id: Optional[str] = None):
    access_token = secrets.token_urlsafe(48)
    expires_dt = utc_now() + timedelta(seconds=SESSION_TTL_SECONDS)
    session = {
        "session_id": uuid.uuid4().hex,
        "access_token": access_token,
        "device_name": device_name or "AYAWrus mobile",
        "device_id": device_id or uuid.uuid4().hex,
        "system_id": SYSTEM_ID,
        "created_at": utc_now().isoformat(),
        "expires_at": expires_dt.isoformat(),
        "expires_at_ts": expires_dt.timestamp(),
        "last_seen": expires_dt.timestamp(),
        "revoked": False,
    }
    with _pairing_lock:
        _mobile_sessions[access_token] = session
        _mobile_sessions_by_system[SYSTEM_ID] = session
    return session


def get_session_for_token(access_token: str):
    _clean_expired_tokens()
    with _pairing_lock:
        session = _mobile_sessions.get(access_token)
        if not session:
            return None
        if session.get("revoked"):
            return None
        if session.get("expires_at_ts", 0) <= time.time():
            _mobile_sessions.pop(access_token, None)
            return None
        session["last_seen"] = time.time()
        return dict(session)


def refresh_session(access_token: str, ttl_seconds: int = SESSION_TTL_SECONDS):
    with _pairing_lock:
        session = _mobile_sessions.get(access_token)
        if not session or session.get("revoked"):
            return None
        expires_dt = utc_now() + timedelta(seconds=ttl_seconds)
        session["expires_at"] = expires_dt.isoformat()
        session["expires_at_ts"] = expires_dt.timestamp()
        session["last_seen"] = time.time()
        return dict(session)


def revoke_session(access_token: str):
    with _pairing_lock:
        session = _mobile_sessions.get(access_token)
        if session:
            session["revoked"] = True
            session["revoked_at"] = utc_now().isoformat()
        _mobile_sessions.pop(access_token, None)
        return True


def revoke_all_sessions():
    with _pairing_lock:
        for token in list(_mobile_sessions.keys()):
            session = _mobile_sessions[token]
            session["revoked"] = True
            session["revoked_at"] = utc_now().isoformat()
        _mobile_sessions.clear()
        _mobile_sessions_by_system.clear()
    return True


def list_active_sessions():
    _clean_expired_tokens()
    with _pairing_lock:
        sessions = []
        for token, session in _mobile_sessions.items():
            if not session.get("revoked"):
                sessions.append({
                    "session_id": session.get("session_id"),
                    "device_name": session.get("device_name"),
                    "device_id": session.get("device_id"),
                    "system_id": session.get("system_id"),
                    "created_at": session.get("created_at"),
                    "expires_at": session.get("expires_at"),
                })
        return sessions


def mobile_status_payload():
    sessions = list_active_sessions()
    return {
        "system_id": SYSTEM_ID,
        "status": "connected" if sessions else "disconnected",
        "connected_devices": len(sessions),
        "sessions": sessions,
    }


def active_mobile_session_count():
    return len(list_active_sessions())


def qr_payload(host: str, port: int = 5000):
    payload = generate_pairing_payload(host=host, port=port)
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
