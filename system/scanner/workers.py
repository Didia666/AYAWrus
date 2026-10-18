
import os
import hashlib

from system.scanner.extractor import get_extractor
from system.scanner.file_scan import classify_file
from system.security.hash_detection import load_malware_hashes


MAX_PE_SIZE = 500 * 1024 * 1024


def extract_worker_batch(file_paths, header_peek_size):
    extractor = get_extractor()
    results = []

    # Load the database once per batch.
    known_hashes = load_malware_hashes()

    for file_path in file_paths:

        # STEP 1: Identify actual PE files.
        kind, header, file_size = classify_file(file_path)

        if kind == "error":
            results.append((
                "read_error",
                file_path,
                None,
                "File could not be inspected"
            ))
            continue

        # STEP 2: Skip all non-PE files.
        if kind != "pe":
            results.append((
                "not_pe",
                file_path,
                None,
                None
            ))
            continue

        # STEP 3: Reject oversized PE files.
        if file_size > MAX_PE_SIZE:
            results.append((
                "not_pe",
                file_path,
                None,
                "PE exceeds scan size limit"
            ))
            continue

        # STEP 4: Read the PE file only once.
        try:
            # The classification header may contain only
            # a portion of the file. Read the complete PE.
            if (
                file_size <= header_peek_size
                and header is not None
                and len(header) == file_size
            ):
                file_bytes = header
            else:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

            # Reject files that changed in size.
            if len(file_bytes) != file_size:
                results.append((
                    "read_error",
                    file_path,
                    None,
                    "File changed during scanning"
                ))
                continue

        except OSError as exc:
            results.append((
                "read_error",
                file_path,
                None,
                str(exc)
            ))
            continue

        # STEP 5: Calculate SHA-256 from memory.
        digest = hashlib.sha256(file_bytes).hexdigest()

        # STEP 6: Check known malicious signatures.
        if digest in known_hashes:
            results.append((
                "hash_malicious",
                file_path,
                digest
            ))
            continue

        # STEP 7: No hash match -> Random Forest features.
        try:
            features = extractor.feature_vector(file_bytes)

        except Exception as exc:
            results.append((
                "extract_error",
                file_path,
                None,
                str(exc)
            ))
            continue

        finally:
            del file_bytes

        # STEP 8: Send features to ML inference.
        results.append((
            "pe",
            file_path,
            features
        ))

    return results
