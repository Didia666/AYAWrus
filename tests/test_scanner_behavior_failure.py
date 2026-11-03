import json

import numpy as np

from system import model_load
from system.history import logs
from system.scanner import file_scan


class DummyMalwareModel:
    expected_input_dim = 1

    def predict_proba(self, features):
        return np.array([[0.9, 0.1]], dtype=np.float32)


class DummyExtractor:
    def feature_vector(self, file_bytes):
        return np.array([0.0], dtype=np.float32)


def test_clean_scan_returns_default_behavior_fields(monkeypatch):
    monkeypatch.setattr(file_scan, "classify_file", lambda path: ("pe", b"MZ", 2))
    monkeypatch.setattr(file_scan, "is_excluded", lambda path, roots: False)
    monkeypatch.setattr(file_scan, "get_extractor", lambda: DummyExtractor())
    monkeypatch.setattr(file_scan, "load_malware_hashes", lambda: {})
    monkeypatch.setattr(file_scan, "classify_malware_probability", lambda probability: "CLEAN")
    monkeypatch.setattr(file_scan, "categorize_threat", lambda probability: "LOW")
    monkeypatch.setattr(file_scan, "record_pe_statistics", lambda **kwargs: None)
    monkeypatch.setattr(model_load, "load_models", lambda: None)
    monkeypatch.setattr(model_load, "model", DummyMalwareModel())
    monkeypatch.setattr(model_load, "selected_feature_indices", None)
    monkeypatch.setattr(model_load, "expected_input_dim", 1)
    monkeypatch.setattr(model_load, "get_behavior_model_metrics", lambda: {})

    result = file_scan.scan_file("sample.exe", auto_quarantine=False)

    assert result["result"] == "CLEAN"
    assert result["behavior_confidence"] == 0.0
    assert result["behavior_scores"] == {}


def test_add_log_entry_persists_behavior_metadata(monkeypatch, tmp_path):
    log_path = tmp_path / "history.json"
    monkeypatch.setattr(logs, "LOG_FILE", str(log_path))
    monkeypatch.setattr(logs, "_buffering_active", False)

    logs.add_log_entry(
        "sample.exe",
        result="SUSPICIOUS",
        behavior_confidence_prob=0.25,
        behavior_confidence=0.5,
        behavior_scores={"ransom": 0.5},
    )

    entry = json.loads(log_path.read_text(encoding="utf-8"))[0]
    assert entry["behavior_confidence_prob"] == 0.25
    assert entry["behavior_confidence"] == 0.5
    assert entry["behavior_scores"] == {"ransom": 0.5}