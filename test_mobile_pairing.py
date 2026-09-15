import json
import sys

from system.mobile_pairing import generate_pairing_payload, revoke_all_sessions
from system.api.server import app


def test_mobile_pairing_flow():
    revoke_all_sessions()
    payload = generate_pairing_payload("192.168.1.25", 5000)
    token = payload["pairing_token"]

    client = app.test_client()
    pair_response = client.post(
        "/api/mobile/pair",
        json={
            "pairing_token": token,
            "device_name": "Galaxy A55",
            "device_id": "device-123",
        },
    )
    assert pair_response.status_code == 200, pair_response.get_data(as_text=True)
    pair_json = pair_response.get_json()
    assert pair_json["success"] is True
    assert "access_token" in pair_json

    status_response = client.get("/api/mobile/status")
    assert status_response.status_code == 200
    status_json = status_response.get_json()
    assert status_json["status"] == "connected"

    auth = {"Authorization": f"Bearer {pair_json['access_token']}"}
    refresh_response = client.post("/api/mobile/session/refresh", headers=auth)
    assert refresh_response.status_code == 200
    refresh_json = refresh_response.get_json()
    assert refresh_json["success"] is True

    disconnect_response = client.post("/api/mobile/disconnect", headers=auth)
    assert disconnect_response.status_code == 200
    assert disconnect_response.get_json()["success"] is True

    final_status = client.get("/api/mobile/status")
    assert final_status.status_code == 200
    assert final_status.get_json()["status"] == "disconnected"


def test_pairing_rejects_expired_or_used_token():
    revoke_all_sessions()
    payload = generate_pairing_payload("192.168.1.25", 5000)
    token = payload["pairing_token"]
    client = app.test_client()

    first = client.post("/api/mobile/pair", json={"pairing_token": token, "device_name": "A", "device_id": "D1"})
    assert first.status_code == 200
    second = client.post("/api/mobile/pair", json={"pairing_token": token, "device_name": "B", "device_id": "D2"})
    assert second.status_code == 400 or second.status_code == 401
