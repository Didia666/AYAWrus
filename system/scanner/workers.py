import os
from thrember.features import PEFeatureExtractor
from system.scanner.extractor import get_extractor



def extract_worker_batch(file_paths, header_peek_size):

    extractor = get_extractor()
    results = []

    for file_path in file_paths:

        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

        except Exception as e:
            results.append(("read_error", file_path, None, str(e)))
            continue

        if file_bytes[:2] != b"MZ":
            results.append(("not_pe", file_path, None, None))
            continue

        try:
            features = extractor.feature_vector(file_bytes)

        except Exception as e:
            results.append(("extract_error", file_path, None, str(e)))
            continue

        # Free the large bytes buffer as soon as possible
        del file_bytes

        results.append((
            "pe",
            file_path,
            features
        ))

    return results
