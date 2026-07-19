import os
from system.scanner.extractor import get_extractor
from system.scanner.file_scan import classify_file



def extract_worker_batch(file_paths, header_peek_size):
    extractor = get_extractor()
    results = []

    for file_path in file_paths:
        kind, header, file_size = classify_file(file_path)

        if kind == "error":
            results.append(("read_error", file_path, None, "stat/open error"))
            continue
        if kind == "skip":
            results.append(("not_pe", file_path, None, None))
            continue
        if kind == "script":
            results.append(("script", file_path))
            continue

        # kind == "pe"
        if file_size <= header_peek_size:
            file_bytes = header
        else:
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
            except Exception as e:
                results.append(("read_error", file_path, None, str(e)))
                continue

        try:
            features = extractor.feature_vector(file_bytes)
        except Exception as e:
            results.append(("extract_error", file_path, None, str(e)))
            continue

        del file_bytes
        results.append(("pe", file_path, features))

    return results