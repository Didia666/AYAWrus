import os
import numpy as np
import random
import threading
from itertools import islice

from concurrent.futures import (
    ProcessPoolExecutor,
    as_completed,
    ThreadPoolExecutor,
    wait,
)
from threading import BoundedSemaphore
from system.scanner.xai_scheduler import schedule_xai
_post_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="AYAWrusPost"
)
_post_slots = BoundedSemaphore(4)
from system.config import SKIP_DIRS, HEADER_PEEK_SIZE, DETECTED_MALWARE
from system.security.exclusions import list_exclusions
from system.security.allowed import allow_threat
from system.scanner.file_scan import scan_text
from system.scanner.workers import *
from system.scanner.pe_statistics import record_pe_statistics
from system.history.logs import add_log_entry
from system.model_load import (
    model,
    selected_feature_indices,
    expected_input_dim,
    get_behavior_prediction_summary,
)
from system.quarantines import quarantine_file
from system.utils import categorize_threat
from system.xai.engine import xai_engine
from system.xai.display import display_xai_explanation
MAX_PENDING = 8


def _record_pe_statistics(file_path, verdict, probability=None, category=None):
    try:
        return record_pe_statistics(
            file_path=file_path,
            verdict=verdict,
            probability=probability,
            category=category,
        )
    except Exception as exc:
        print(f"[PE statistics] Could not save analysis for {file_path}: {exc}")
        return None


def submit_post_process(fn):
    # Apply backpressure rather than dropping
    # quarantine or notification tasks.
    _post_slots.acquire()

    try:
        future = _post_executor.submit(fn)
    except Exception:
        _post_slots.release()
        raise

    future.add_done_callback(
        lambda completed: _post_slots.release()
    )

    return future


def locally_shuffled(iterable, buffer_size=500, rng=None):
    """Breaks up directory-level size clustering without a full sort
    or any getsize() calls — keeps memory bounded to buffer_size paths.
    Pass rng=random.Random(seed) for reproducible/testable ordering."""
    if rng is None:
        rng = random

    it = iter(iterable)
    buf = list(islice(it, buffer_size))
    rng.shuffle(buf)

    for item in it:
        idx = rng.randrange(len(buf))
        yield buf[idx]
        buf[idx] = item

    rng.shuffle(buf)
    for item in buf:
        yield item

def iter_files(folder_path, excluded_roots):
    for root, dirs, files in os.walk(folder_path):
        root_lower = os.path.abspath(root).lower()

        if any(root_lower.startswith(skip.lower()) for skip in SKIP_DIRS):
            continue

        if any(root_lower.startswith(ex) for ex in excluded_roots):
            continue

        for file in files:
            full_path = os.path.join(root, file)
            full_lower = os.path.abspath(full_path).lower()

            if any(full_lower.startswith(ex) for ex in excluded_roots):
                continue

            yield full_path

def chunked(iterator, size):
    iterator = iter(iterator)

    while True:
        batch = list(islice(iterator, size))

        if not batch:
            break

        yield batch

def process_batch_results(batch_results, pe_candidates, excluded_roots):
    for item in batch_results:
        kind, f = item[0], item[1]
        if kind == "hash_malicious":
            digest = item[2]

            add_log_entry(
                f,
                result="MALICIOUS",
                details=f"SHA-256 signature match: {digest}"
            )

            DETECTED_MALWARE.append(f)

            try:
                quarantine_result = quarantine_file(f)
                print(
                    f"[SHA256] {f}: {quarantine_result}"
                )
            except Exception as exc:
                print(
                    f"[SHA256] Quarantine failed: {exc}"
                )

            continue


        if kind == "pe":
            features = item[2]
            pe_candidates.append((f, features))

        elif kind == "script":
            result = scan_text(f, excluded_roots=excluded_roots)
            print(result)

            if (
                result.get("result") == "SUSPICIOUS"
                and result.get("xai_report")
            ):
                display_xai_explanation(result["xai_report"])

        elif kind == "extract_error":
            extra = item[3]
            add_log_entry(
                f,
                result="ERROR",
                details=f"PE extraction failed: {extra[:50] if extra else ''}"
            )

        elif kind in ("read_error", "error", "not_pe"):
            pass

def scan_folder_parallel(folder_path, batch_size=64, pool=None, extract_chunk_size=32):
    pending = []
    post_futures = []
    excluded_roots = [os.path.abspath(e).lower() for e in list_exclusions()]  # loaded ONCE

    pe_candidates = []

    owns_pool = pool is None
    if owns_pool:
        pool = ProcessPoolExecutor(max_workers=min(6, os.cpu_count()))

    def run_inference_batch(chunk):
        """Same Phase-2 logic as before, just callable mid-scan instead
        of only after every extraction future has finished."""
        if model is None:
            for f, _ in chunk:
                add_log_entry(f, result="UNKNOWN", details="Model not loaded")
                _record_pe_statistics(f, "UNKNOWN")
            return

        X = np.asarray([c[1] for c in chunk], dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        if selected_feature_indices is not None:
            if X.shape[1] > selected_feature_indices.max():
                X = X[:, selected_feature_indices]
            else:
                for f, _ in chunk:
                    add_log_entry(f, result="ERROR",
                                  details="Feature schema mismatch — extractor/model version drift")
                    _record_pe_statistics(f, "ERROR")
                return

        expected_dim = getattr(model, "expected_input_dim", expected_input_dim)
        if expected_dim is not None:
            if X.shape[1] > expected_dim:
                X = X[:, :expected_dim]
            elif X.shape[1] < expected_dim:
                X = np.pad(X, ((0, 0), (0, expected_dim - X.shape[1])), mode="constant")

        if X.shape[1] != getattr(model, "expected_input_dim", expected_input_dim or X.shape[1]):
            for f, _ in chunk:
                add_log_entry(f, result="ERROR", details="Feature schema mismatch — extractor/model version drift")
                _record_pe_statistics(f, "ERROR")
            return

        try:
            probs = model.predict_proba(X)[:, 1]
        except Exception as e:
            for f, _ in chunk:
                add_log_entry(f, result="ERROR", details=f"Prediction failed: {e}")
                _record_pe_statistics(f, "ERROR")
            return

        for (f, features), prob in zip(chunk, probs):
            prob = float(prob)
            pred = 1.0 if prob >= 0.5 else 0.0
            category = categorize_threat(prob)
            result_str = "MALICIOUS" if pred == 1 else "CLEAN"
            _record_pe_statistics(
                f,
                result_str,
                probability=prob,
                category=category,
            )

            if pred == 1:
                behavior_probability = 0.0
                behavior_result = "NOT_EVALUATED"
                behavior_types = []
                behavior_type = None

                try:
                    # Original feature vector from the batch.
                    raw_features = np.asarray(
                        features,
                        dtype=np.float32
                    ).reshape(1, -1)

                    # One inference call only.
                    behavior_summary = get_behavior_prediction_summary(
                        raw_features
                    )

                    behavior_probability = float(
                        behavior_summary.get("mean_probability", 0.0)
                    )

                    behavior_types = behavior_summary.get(
                        "predicted_labels", []
                    )

                    behavior_type = behavior_summary.get("top_label")

                    behavior_result = (
                        "BEHAVIORAL_ANOMALY"
                        if behavior_types
                        else "NO_BEHAVIOR_LABEL_PREDICTED"
                    )

                except Exception as e:
                    print(
                        f"Behavior model evaluation failed for {f}: {e}"
                    )

                    behavior_probability = 0.0
                    behavior_result = "BEHAVIOR_ERROR"
                    behavior_types = []
                    behavior_type = None

                DETECTED_MALWARE.append(f)
                add_log_entry(
                    f,
                    result="MALICIOUS",
                    probability=prob,
                    details=(
                        f"Category: {category}; behavior_probability={behavior_probability:.3f}; "
                        f"behavior_result={behavior_result}; behavior_types={','.join(behavior_types) if behavior_types else 'unknown'}"
                    ),
                    behavior_confidence=behavior_probability,
                    behavior_type=behavior_type,
                    behavior_types=behavior_types,
                    behavior_result=behavior_result,
                )

                
                def _post_process_malware(
                    file_path=f,
                    file_prob=prob,
                    file_category=category,
                ):
                    """
                    Background security post-processing.

                    No Telegram calls.
                    No XAI scheduling before quarantine.
                    """

                    try:
                        if file_prob >= 0.90:
                            # Security action first.
                            quarantine_result = quarantine_file(file_path)

                            if not (
                                isinstance(quarantine_result, str)
                                and (
                                    "MOVED TO QUARANTINE" in quarantine_result
                                    or "ALREADY IN QUARANTINE" in quarantine_result
                                )
                            ):
                                raise RuntimeError(
                                    f"Quarantine did not succeed: {quarantine_result}"
                                )

                            print(
                                f"[Security] Quarantine confirmed: {file_path}"
                            )

                        else:
                            # Preserves the existing policy.
                            allow_threat(
                                file_path,
                                file_category,
                                "MALICIOUS"
                            )

                            print(
                                f"[Security] Existing allow policy "
                                f"applied: {file_path}"
                            )

                        return True

                    except Exception as e:
                        print(
                            f"[Security] Post-processing failed "
                            f"for {file_path}: {e}"
                        )
                        return False


                # Submit to the bounded post-processing executor.
                future = submit_post_process(
                    _post_process_malware
                )

                post_futures.append(future)

    def drain_one_pending():
        """Pull one finished future, process its results, and flush
        inference batches as soon as they're full — called both while
        still submitting new chunks and during final drain."""
        done = next(as_completed(pending))
        pending.remove(done)
        try:
            batch_results = done.result()
            process_batch_results(batch_results, pe_candidates, excluded_roots)
        except Exception as e:
            print(f"Error processing batch: {e}")
            return

        while len(pe_candidates) >= batch_size:
            run_inference_batch(pe_candidates[:batch_size])
            del pe_candidates[:batch_size]

    try:
        file_iter = locally_shuffled(
            iter_files(folder_path, excluded_roots),
            buffer_size=500
        )
        for chunk in chunked(file_iter, extract_chunk_size):
            pending.append(pool.submit(extract_worker_batch, chunk, HEADER_PEEK_SIZE))

            if len(pending) >= MAX_PENDING:
                drain_one_pending()

        while pending:
            drain_one_pending()
    finally:
        if owns_pool:
            pool.shutdown(wait=True)

    # leftover partial batch smaller than batch_size
    if pe_candidates and model is not None:
        run_inference_batch(pe_candidates)
    elif pe_candidates and model is None:
        for f, _ in pe_candidates:
            add_log_entry(f, result="UNKNOWN", details="Model not loaded")

    
    # Wait for outstanding security post-processing jobs.
    if post_futures:
        print(
            f"[Security] Waiting for "
            f"{len(post_futures)} submitted tasks."
        )

        wait(post_futures)

        failed_count = 0

        for future in post_futures:
            try:
                success = future.result()

                if not success:
                    failed_count += 1

            except Exception as e:
                failed_count += 1
                print(
                    f"[Security] Worker exception: {e}"
                )

        if failed_count:
            print(
                f"[Security] WARNING: "
                f"{failed_count} post-processing tasks "
                f"reported failure."
            )

        else:
            print(
                "[Security] All submitted "
                "post-processing tasks finished."
            )
