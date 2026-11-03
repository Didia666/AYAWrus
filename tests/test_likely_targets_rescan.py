from contextlib import nullcontext

import numpy as np

from system import model_load
from system.scanner import file_scan
from ui import scan
from ui import scan_targets


class DummyMalwareModel:
    expected_input_dim = 1

    def predict_proba(self, features):
        return np.array([[0.05, 0.95]], dtype=np.float32)


class DummyExtractor:
    def feature_vector(self, file_bytes):
        return np.array([0.0], dtype=np.float32)


def _setup_worker(monkeypatch, file_path, threat):
    results = []
    key = scan._normalize_target_path(file_path)
    monkeypatch.setitem(scan.LIKELY_TARGETS_CONTEXT, key, threat)
    monkeypatch.setattr(scan.dpg, "mutex", nullcontext)
    monkeypatch.setattr(
        scan,
        "set_likely_targets_data",
        lambda data, path=None: results.append((data, path)),
    )
    return results


def _discovery_result():
    return {
        "state": "done",
        "scan_complete": True,
        "files_scanned": 4,
        "files_skipped_permission": 0,
        "at_risk_count": 1,
        "last_scanned": "13:00",
        "categories": {
            "documents": {
                "support_score": 0.8,
                "source": "behavior_mapping",
                "count": 1,
            }
        },
        "flagged": ["documents"],
        "by_folder": {},
        "files": [
            {
                "path": "C:\\Users\\test\\Documents\\report.pdf",
                "category": "documents",
                "support_score": 0.8,
                "associated_behaviors": ["ransom", "wiper"],
                "reason": "Matched file extension .pdf",
            }
        ],
    }


def test_likely_targets_discovery_preserves_multiple_confirmed_behaviors(monkeypatch):
    file_path = "C:\\samples\\threat.exe"
    results = _setup_worker(
        monkeypatch,
        file_path,
        {
            "behavior_types": ["ransom", "wiper"],
            "behavior_scores": {"ransom": 0.8, "wiper": 0.7},
            "behavior_confidence": 0.8,
        },
    )
    captured = {}

    def discover(**kwargs):
        captured.update(kwargs)
        return _discovery_result()

    monkeypatch.setattr(scan, "discover_likely_targets", discover)

    scan._likely_targets_worker(file_path)

    assert captured["impact_result"]["behaviors"]
    assert [b["label"] for b in captured["impact_result"]["behaviors"]] == [
        "ransom",
        "wiper",
    ]
    assert results[0][0]["state"] == "loading"
    assert results[-1][0]["state"] == "done"
    file_result = results[-1][0]["files"][0]
    assert file_result["category"] == "documents"
    assert file_result["associated_behaviors"] == ["ransom", "wiper"]


def test_likely_targets_reports_search_progress(monkeypatch):
    file_path = "C:\\samples\\progress.exe"
    results = _setup_worker(
        monkeypatch,
        file_path,
        {
            "behavior_types": ["ransom"],
            "behavior_scores": {"ransom": 0.8},
            "behavior_confidence": 0.8,
        },
    )

    def discover(**kwargs):
        kwargs["progress_callback"](1250, 7)
        return _discovery_result()

    monkeypatch.setattr(scan, "discover_likely_targets", discover)

    scan._likely_targets_worker(file_path)

    progress = next(
        data for data, _ in results
        if data.get("files_scanned") == 1250
    )
    assert progress["at_risk_count"] == 7
    assert "1,250 files checked" in progress["message"]
    assert "7 matches so far" in progress["message"]
    assert "Files are not opened" in progress["message"]


def test_likely_targets_discovery_marks_low_score_candidate_unconfirmed(monkeypatch):
    file_path = "C:\\samples\\candidate.exe"
    results = _setup_worker(
        monkeypatch,
        file_path,
        {
            "behavior_types": [],
            "behavior_type": "ransom",
            "behavior_scores": {"ransom": 0.31},
            "behavior_confidence": 0.31,
        },
    )
    monkeypatch.setattr(
        scan,
        "discover_likely_targets",
        lambda **kwargs: _discovery_result(),
    )

    scan._likely_targets_worker(file_path)

    data = results[-1][0]
    assert data["state"] == "candidate"
    assert data["prediction_mode"] == "candidate"
    assert data["candidate_label"] == "ransom"
    assert data["candidate_score"] == 0.31
    assert "Unconfirmed behavior candidate" in data["message"]
    assert "not confirmed affected files" in data["message"]


def test_likely_targets_without_behavior_prediction_skips_discovery(monkeypatch):
    file_path = "C:\\samples\\no-behavior.exe"
    results = _setup_worker(
        monkeypatch,
        file_path,
        {
            "behavior_types": [],
            "behavior_scores": {},
            "behavior_type": None,
        },
    )
    discovery_calls = []
    monkeypatch.setattr(
        scan,
        "discover_likely_targets",
        lambda **kwargs: discovery_calls.append(kwargs),
    )

    scan._likely_targets_worker(file_path)

    data = results[-1][0]
    assert data["state"] == "no_behavior"
    assert "usable behavior prediction" in data["message"].lower()
    assert discovery_calls == []


def test_no_behavior_state_is_rendered_as_explanation(monkeypatch):
    rendered = []
    monkeypatch.setattr(
        scan_targets,
        "_empty_state",
        lambda *args: rendered.append(args),
    )

    scan_targets._render_list_area(
        "no_behavior",
        {"files": []},
        "The behavior model did not return a usable behavior prediction.",
    )

    assert rendered
    assert "usable behavior prediction" in rendered[0][2]
    assert "confirmed behavior prediction" in rendered[0][3]


def test_likely_targets_rescan_reclassifies_without_scan_side_effects(
    monkeypatch,
    tmp_path,
):
    file_path = tmp_path / "threat.exe"
    file_path.write_bytes(b"MZ")
    results = _setup_worker(
        monkeypatch,
        str(file_path),
        {"behavior_types": ["ransom"]},
    )
    scan_calls = []
    threat = {
        "result": "MALICIOUS",
        "file_path": str(file_path),
        "behavior_types": ["ransom", "wiper"],
        "behavior_scores": {"ransom": 0.8, "wiper": 0.7},
        "behavior_confidence": 0.8,
    }

    def scan_without_side_effects(path, **kwargs):
        scan_calls.append((path, kwargs))
        return threat

    monkeypatch.setattr(scan.sf, "scan_file", scan_without_side_effects)
    monkeypatch.setattr(
        scan,
        "discover_likely_targets",
        lambda **kwargs: _discovery_result(),
    )

    scan._likely_targets_worker(str(file_path), rescan=True)

    assert scan_calls == [
        (str(file_path), {"auto_quarantine": False, "analysis_only": True})
    ]
    assert results[0][0]["state"] == "loading"
    assert results[-1][0]["state"] == "done"
    assert results[-1][0]["files"][0]["associated_behaviors"] == [
        "ransom",
        "wiper",
    ]


def test_analysis_only_scan_does_not_log_quarantine_or_schedule_xai(monkeypatch):
    monkeypatch.setattr(file_scan, "classify_file", lambda path: ("pe", b"MZ", 2))
    monkeypatch.setattr(file_scan, "is_excluded", lambda path, roots: False)
    monkeypatch.setattr(file_scan, "get_extractor", lambda: DummyExtractor())
    monkeypatch.setattr(file_scan, "load_malware_hashes", lambda: {})
    monkeypatch.setattr(file_scan, "record_pe_statistics", lambda **kwargs: None)
    monkeypatch.setattr(model_load, "load_models", lambda: None)
    monkeypatch.setattr(model_load, "model", DummyMalwareModel())
    monkeypatch.setattr(model_load, "selected_feature_indices", None)
    monkeypatch.setattr(model_load, "expected_input_dim", 1)
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
            "predicted_labels": ["ransom", "wiper"],
            "label_scores": {"ransom": 0.8, "wiper": 0.7},
            "top_label": "ransom",
        },
    )
    monkeypatch.setattr(model_load, "get_behavior_model_metrics", lambda: {})

    side_effects = []
    for name in (
        "add_log_entry",
        "quarantine_file",
        "schedule_xai",
        "new_detection_id",
        "enqueue_threat_notification",
    ):
        monkeypatch.setattr(
            file_scan,
            name,
            lambda *args, _name=name, **kwargs: side_effects.append(_name),
        )

    result = file_scan.scan_file("sample.exe", analysis_only=True)

    assert result["analysis_only"] is True
    assert result["result"] == "MALICIOUS"
    assert result["behavior_types"] == ["ransom", "wiper"]
    assert side_effects == []
