import os
from thrember.features import PEFeatureExtractor
from system.scanner.extractor import get_extractor



def extract_worker_batch(file_paths, header_peek_size):
    """Process a batch of files in one worker task instead of one task per file,
    cutting inter-process communication overhead roughly by the batch size."""
    extractor = get_extractor()
    results = []
    for file_path in file_paths:
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, "rb") as f:
                header = f.read(header_peek_size)
        except Exception:
            results.append(("error", file_path, None, None))
            continue

        if header[:2] != b'MZ':
            results.append(("not_pe", file_path, None, None))
            continue

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
        results.append((
            "pe",
            file_path,
            features
        ))
    return results

