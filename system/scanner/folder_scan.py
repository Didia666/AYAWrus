import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

from system.config import SKIP_DIRS, HEADER_PEEK_SIZE, DETECTED_MALWARE
from system.security.exclusions import list_exclusions
from system.security.allowed import allow_threat
from system.scanner.file_scan import scan_text
from system.scanner.workers import *
from system.history.logs import add_log_entry
from system.model_load import model, selected_feature_indices
from system.quarantines import quarantine_file
from system.notifications import send_telegram_notification
from system.utils import categorize_threat
from system.xai.engine import xai_engine
from system.xai.display import display_xai_explanation

def scan_folder_parallel(folder_path, batch_size=64, pool=None, extract_chunk_size=32):
    excluded_roots = [os.path.abspath(e).lower() for e in list_exclusions()]  # loaded ONCE
    files_to_scan = []
    for root, dirs, files in os.walk(folder_path):
        root_lower = os.path.abspath(root).lower()
        if any(root_lower.startswith(skip.lower()) for skip in SKIP_DIRS):
            continue
        if any(root_lower.startswith(ex_root) for ex_root in excluded_roots):
            continue
        for file in files:
            full_path = os.path.join(root, file)
            full_lower = os.path.abspath(full_path).lower()
            if any(full_lower.startswith(ex_root) for ex_root in excluded_roots):
                continue
            files_to_scan.append(full_path)

    pe_candidates = []

    owns_pool = pool is None
    if owns_pool:
        pool = ProcessPoolExecutor(max_workers=os.cpu_count() - 1)

    try:
        files_to_scan.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
        chunks = [files_to_scan[i:i + extract_chunk_size]
                  for i in range(0, len(files_to_scan), extract_chunk_size)]
        futures = [pool.submit(extract_worker_batch, chunk, HEADER_PEEK_SIZE) for chunk in chunks]
        for future in as_completed(futures):
            try: 
                batch_results = future.result()
            except Exception as e:
                print(f"Error processing batch: {e}")
            for item in batch_results:
                kind, f = item[0], item[1]

                if kind == "pe":
                    features = item[2]
                    pe_candidates.append((f, features))
                elif kind == "script":
                    result = scan_text(f, excluded_roots=excluded_roots)
                    print(result)
                    if result.get("result") in ("SUSPICIOUS",) and result.get("xai_report"):
                        display_xai_explanation(result["xai_report"])
                elif kind == "extract_error":
                    extra = item[3]
                    add_log_entry(f, result="ERROR", details=f"PE extraction failed: {extra[:50] if extra else ''}")
                elif kind in ("read_error", "error", "not_pe"):
                    pass  # already effectively CLEAN/ERROR, nothing to batch
    finally:
        if owns_pool:
            pool.shutdown(wait=True)

    # --- Phase 2: batch model inference ---
    if not pe_candidates or model is None:
        if pe_candidates and model is None:
            for f, _ in pe_candidates:
                add_log_entry(f, result="UNKNOWN", details="Model not loaded")
        return

    for i in range(0, len(pe_candidates), batch_size):
        chunk = pe_candidates[i:i + batch_size]
        X = np.array([c[1] for c in chunk])
        if selected_feature_indices is not None:
            if X.shape[1] > selected_feature_indices.max():
                X = X[:, selected_feature_indices]
            else:
                for f, _ in chunk:
                    add_log_entry(f, result="ERROR",
                                  details="Feature schema mismatch — extractor/model version drift")
                continue

        try:
            probs = model.predict_proba(X)[:, 1]      # one call for the whole chunk
            preds = model.predict(X)
        except Exception as e:
            for f, _ in chunk:
                add_log_entry(f, result="ERROR", details=f"Prediction failed: {e}")
            continue

        # --- Phase 3: per-file bookkeeping (cheap, no model calls) ---
        for (f, features), prob, pred in zip(chunk, probs, preds):
            prob = float(prob)
            pred = float(pred)
            category = categorize_threat(prob)
            result_str = "MALICIOUS" if pred == 1 else "CLEAN"

            xai_report = None
            if result_str == "MALICIOUS":   # only build XAI for interesting files (also fixes advice #6)
                try:
                    with open(f, "rb") as file:
                        file_bytes = file.read()

                    xai_report = xai_engine.analyze_file(
                        f,
                        file_bytes,
                        features,
                        prob,
                        result_str
                    )

                except Exception as e:
                    print(f"XAI failed: {e}")

            if pred == 1:
                DETECTED_MALWARE.append(f)
                add_log_entry(f, result="MALICIOUS", probability=prob, details=f"Category: {category}")
                message = (
                    f"[!] Malware Detected!\nFile: {os.path.basename(f)}\n"
                    f"Path: {f}\nProbability: {prob:.2%}\nSeverity: {category}"
                )
                send_telegram_notification(message)
                if prob >= 0.90:
                    quarantine_file(f)
                else:
                    allow_threat(f, category, "MALICIOUS")
                print({"result": "MALICIOUS", "probability": prob, "file_path": f, "category": category})
                if xai_report:
                    display_xai_explanation(xai_report)
            else:
                print({"result": "CLEAN", "probability": prob, "file_path": f})
