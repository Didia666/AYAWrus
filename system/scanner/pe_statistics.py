import json
import math
import os
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone

from system.history.batches import current_batch_id


PE_STATISTICS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pe_statistics.json",
)
_PE_STATISTICS_LOCK = threading.Lock()
_HIGH_ENTROPY_THRESHOLD = 7.0


def _entropy(data):
    if not data:
        return 0.0
    length = len(data)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in Counter(data).values()
    )


def build_pe_statistics(
    file_path,
    verdict,
    probability=None,
    category=None,
    file_bytes=None,
):
    if file_bytes is None:
        with open(file_path, "rb") as source:
            file_bytes = source.read()

    file_size = len(file_bytes)
    stats = {
        "scan_id": uuid.uuid4().hex,
        "batch_id": current_batch_id(),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "file_path": os.path.abspath(file_path),
        "verdict": str(verdict).upper(),
        "probability": float(probability) if probability is not None else None,
        "category": category,
        "file_size": file_size,
        "entropy": round(_entropy(file_bytes), 3),
        "architecture": None,
        "section_count": None,
        "dll_count": None,
        "import_count": None,
        "high_entropy_sections": 0,
        "high_entropy_section_names": [],
        "dll_names": [],
        "is_pe": False,
        "parse_status": "NOT_PE",
        "parse_error": None,
    }

    try:
        import pefile

        pe = pefile.PE(data=file_bytes)
        machine_names = {
            0x014C: "x86",
            0x8664: "x64",
            0x01C0: "ARM",
            0x01C2: "THUMB",
            0x01C4: "ARMv7",
            0xAA64: "ARM64",
        }
        stats["is_pe"] = True
        stats["parse_status"] = "OK"
        stats["architecture"] = machine_names.get(
            pe.FILE_HEADER.Machine,
            f"unknown (0x{pe.FILE_HEADER.Machine:04X})",
        )
        stats["section_count"] = len(pe.sections)

        high_entropy_sections = []
        for section in pe.sections:
            section_entropy = float(section.get_entropy())
            if section_entropy > _HIGH_ENTROPY_THRESHOLD:
                section_name = (
                    section.Name.decode("utf-8", errors="replace")
                    .strip("\x00")
                    or "<unnamed>"
                )
                high_entropy_sections.append({
                    "name": section_name,
                    "entropy": round(section_entropy, 3),
                })
        stats["high_entropy_sections"] = len(high_entropy_sections)
        stats["high_entropy_section_names"] = high_entropy_sections

        imports = getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
        dll_names = []
        import_count = 0
        for entry in imports:
            dll_name = entry.dll
            if dll_name:
                dll_names.append(
                    dll_name.decode("utf-8", errors="replace")
                    if isinstance(dll_name, bytes)
                    else str(dll_name)
                )
            import_count += len(entry.imports)
        stats["dll_names"] = sorted(set(dll_names), key=str.casefold)
        stats["dll_count"] = len(imports)
        stats["import_count"] = import_count
    except Exception as exc:
        stats["parse_status"] = "ERROR" if file_bytes.startswith(b"MZ") else "NOT_PE"
        if stats["parse_status"] == "ERROR":
            stats["parse_error"] = str(exc)[:500]

    return stats


def append_pe_statistics(stats):
    """Append one PE statistics record, replacing the JSON atomically."""
    with _PE_STATISTICS_LOCK:
        if os.path.exists(PE_STATISTICS_FILE):
            with open(PE_STATISTICS_FILE, "r", encoding="utf-8") as source:
                contents = source.read().strip()
            if not contents:
                records = []
            else:
                data = json.loads(contents)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and isinstance(data.get("records"), list):
                    records = data["records"]
                else:
                    raise ValueError(
                        f"Unsupported PE statistics document in {PE_STATISTICS_FILE}"
                    )
        else:
            records = []

        records.append(stats)
        document = {
            "schema_version": 1,
            "records": records,
        }
        temp_path = f"{PE_STATISTICS_FILE}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as target:
                json.dump(document, target, indent=2, ensure_ascii=False)
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, PE_STATISTICS_FILE)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def record_pe_statistics(
    file_path,
    verdict,
    probability=None,
    category=None,
    file_bytes=None,
):
    stats = build_pe_statistics(
        file_path=file_path,
        verdict=verdict,
        probability=probability,
        category=category,
        file_bytes=file_bytes,
    )
    append_pe_statistics(stats)
    return stats
