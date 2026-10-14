import json

from system.scanner import pe_statistics


def test_build_pe_statistics_records_file_basics_and_parse_status():
    stats = pe_statistics.build_pe_statistics(
        file_path="sample.exe",
        verdict="MALICIOUS",
        probability=0.91,
        category="SEVERE",
        file_bytes=b"MZnot-a-valid-pe",
    )

    assert stats["verdict"] == "MALICIOUS"
    assert stats["probability"] == 0.91
    assert stats["file_size"] == len(b"MZnot-a-valid-pe")
    assert stats["entropy"] >= 0
    assert stats["is_pe"] is False
    assert stats["parse_status"] == "ERROR"
    assert stats["parse_error"]
    assert stats["section_count"] is None
    assert stats["high_entropy_sections"] == 0


def test_append_pe_statistics_preserves_records_and_writes_json(tmp_path, monkeypatch):
    output_path = tmp_path / "pe_statistics.json"
    monkeypatch.setattr(pe_statistics, "PE_STATISTICS_FILE", str(output_path))
    first = {"scan_id": "scan-1", "file_path": "one.exe"}
    second = {"scan_id": "scan-2", "file_path": "two.exe"}

    pe_statistics.append_pe_statistics(first)
    pe_statistics.append_pe_statistics(second)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert saved["records"] == [first, second]
    assert not list(tmp_path.glob("*.tmp"))
