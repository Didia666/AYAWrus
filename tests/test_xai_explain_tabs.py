import numpy as np

from system import model_load
from system.scanner import file_scan, xai_scheduler
from ui import scan_explain


class DummyMalwareModel:
    expected_input_dim = 1

    def predict_proba(self, features):
        return np.array([[0.05, 0.95]], dtype=np.float32)


class DummyExtractor:
    def feature_vector(self, file_bytes):
        return np.array([0.0], dtype=np.float32)


def test_normal_malicious_scan_schedules_xai_with_file_snapshot(monkeypatch):
    monkeypatch.setattr(file_scan, "classify_file", lambda path: ("pe", b"MZ", 2))
    monkeypatch.setattr(file_scan, "is_excluded", lambda path, roots: False)
    monkeypatch.setattr(file_scan, "get_extractor", lambda: DummyExtractor())
    monkeypatch.setattr(file_scan, "load_malware_hashes", lambda: {})
    monkeypatch.setattr(file_scan, "record_pe_statistics", lambda **kwargs: None)
    monkeypatch.setattr(model_load, "load_models", lambda: None)
    monkeypatch.setattr(model_load, "model", DummyMalwareModel())
    monkeypatch.setattr(model_load, "selected_feature_indices", None)
    monkeypatch.setattr(model_load, "expected_input_dim", 1)
    monkeypatch.setattr(model_load, "get_behavior_model_metrics", lambda: {})
    monkeypatch.setattr(
        file_scan,
        "classify_malware_probability",
        lambda probability: "MALICIOUS",
    )
    monkeypatch.setattr(file_scan, "categorize_threat", lambda probability: "HIGH")
    monkeypatch.setattr(
        file_scan,
        "get_behavior_prediction_summary",
        lambda features: {
            "mean_probability": 0.75,
            "max_score": 0.8,
            "predicted_labels": ["ransom"],
            "label_scores": {"ransom": 0.8},
            "top_label": "ransom",
        },
    )
    monkeypatch.setattr(file_scan, "new_detection_id", lambda: "detection-1")
    monkeypatch.setattr(file_scan, "add_log_entry", lambda *args, **kwargs: None)
    scheduled = {}

    def schedule(**kwargs):
        scheduled.update(kwargs)
        return "detection-1"

    monkeypatch.setattr(file_scan, "schedule_xai", schedule)
    monkeypatch.setattr(file_scan, "quarantine_file", lambda path: "MOVED TO QUARANTINE")
    monkeypatch.setattr(file_scan, "enqueue_threat_notification", lambda *args: None)
    monkeypatch.setattr(file_scan, "DETECTED_MALWARE", [])

    result = file_scan.scan_file("sample.exe", auto_quarantine=True)

    assert result["xai_job_id"] == "detection-1"
    assert scheduled["file_path"] == "sample.exe"
    assert scheduled["file_bytes"] == b"MZ"
    assert scheduled["detection_id"] == "detection-1"


def test_xai_worker_uses_snapshot_if_original_file_is_gone(monkeypatch):
    analyzed = {}
    stored = {}

    class DummyEngine:
        def analyze_file(self, file_path, file_bytes, features, probability, result):
            analyzed["values"] = (
                file_path,
                file_bytes,
                features,
                probability,
                result,
            )
            return {"scan_steps": [{"title": "done"}]}

    monkeypatch.setattr(xai_scheduler, "XAIExplanationEngine", DummyEngine)
    monkeypatch.setattr(
        xai_scheduler,
        "_store_report",
        lambda detection_id, report: stored.update(
            detection_id=detection_id,
            report=report,
        ),
    )

    xai_scheduler._analyze(
        "job-1",
        "no-longer-present.exe",
        [1.0],
        0.99,
        "MALICIOUS",
        b"captured PE bytes",
    )

    assert analyzed["values"][1] == b"captured PE bytes"
    assert stored["detection_id"] == "job-1"
    assert stored["report"]["scan_steps"] == [{"title": "done"}]


def test_explain_popup_rebuilds_empty_tabs_when_xai_report_is_ready(monkeypatch):
    report = {
        "scan_steps": [{"title": "Checking", "description": "Complete"}],
        "pe_analysis": {"is_pe": True},
        "recommendations": ["Review this file"],
        "educational_topics": {"pe": {"title": "PE", "content": "About PE"}},
    }
    refreshed = []
    monkeypatch.setitem(scan_explain._s, "report_pending", True)
    monkeypatch.setitem(scan_explain._s, "report_poll_at", 0.0)
    monkeypatch.setitem(scan_explain._s, "report_job_id", "job-2")
    monkeypatch.setattr(scan_explain, "get_xai_report", lambda job_id: report)
    monkeypatch.setattr(
        scan_explain,
        "_refresh_report_pages",
        lambda completed: refreshed.append(completed),
    )

    scan_explain._poll_xai_report(1.0)

    assert not scan_explain._s["report_pending"]
    assert refreshed == [report]


def test_explain_popup_shows_xai_error_instead_of_empty_tabs(monkeypatch):
    refreshed = []
    monkeypatch.setitem(scan_explain._s, "report_pending", True)
    monkeypatch.setitem(scan_explain._s, "report_poll_at", 0.0)
    monkeypatch.setitem(scan_explain._s, "report_job_id", "job-3")
    monkeypatch.setattr(scan_explain, "get_xai_report", lambda job_id: None)
    monkeypatch.setattr(
        scan_explain,
        "get_xai_status",
        lambda job_id: {"status": "ERROR", "error": "model unavailable"},
    )
    monkeypatch.setattr(
        scan_explain,
        "_refresh_report_pages",
        lambda completed: refreshed.append(completed),
    )

    scan_explain._poll_xai_report(1.0)

    assert not scan_explain._s["report_pending"]
    assert "model unavailable" in refreshed[0]["_xai_error"]
    assert "Generating" not in scan_explain._report_empty_message(
        refreshed[0],
        "No actions",
    )
