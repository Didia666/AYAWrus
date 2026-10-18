import os
import numpy as np
import threading
from system.config import HEADER_PEEK_SIZE, KNOWN_SCRIPT_EXTS, KNOWN_SKIP_EXTS, DETECTED_MALWARE, DETECTED_SUSPICIOUS, SUS_WRODS
from system.security.exclusions import is_excluded
from system.security.allowed import allow_threat
from system.scanner.extractor import get_extractor
from system.scanner.pe_statistics import record_pe_statistics
from system.history.logs import add_log_entry
import hashlib
from system.security.hash_detection import load_malware_hashes
from system.model_load import (
    model,
    selected_feature_indices,
    expected_input_dim,
    get_behavior_prediction_summary,
    get_behavior_model_metrics,
)
from system.scanner.xai_scheduler import (
    schedule_xai,
    new_detection_id,
)
from system.quarantines.quarantine import quarantine_file
from system.utils.utility import categorize_threat
from system.notifications import enqueue_threat_notification
from system.xai.engine import xai_engine


def classify_file(file_path):
    """
    Classify using the real Windows PE header.

    Returns:
        ("pe", header, file_size)
        ("skip", None, file_size)
        ("error", None, 0)

    File extensions are not trusted.
    """
    try:
        file_size = os.path.getsize(file_path)

        # Minimum size needed for DOS header + PE signature.
        if file_size < 64:
            return ("skip", None, file_size)

        with open(file_path, "rb") as f:
            header = f.read(HEADER_PEEK_SIZE)

            # Check DOS MZ signature.
            if header[:2] != b"MZ":
                return ("skip", None, file_size)

            # e_lfanew is at offset 0x3C (60).
            pe_offset = int.from_bytes(
                header[0x3C:0x40],
                byteorder="little"
            )

            # Reject impossible PE header locations.
            if (
                pe_offset < 64
                or pe_offset > file_size - 24
                or pe_offset > 1024 * 1024
            ):
                return ("skip", None, file_size)

            # Check the actual PE signature.
            f.seek(pe_offset)
            signature = f.read(4)

            if signature != b"PE\x00\x00":
                return ("skip", None, file_size)

            return ("pe", header, file_size)

    except OSError as exc:
        print(f"[PE Check] Cannot read {file_path}: {exc}")
        return ("error", None, 0)

def _prepare_model_features(features):
    X = np.asarray(features, dtype=np.float32)
    if X.ndim == 1:
        X = X.reshape(1, -1)

    if selected_feature_indices is not None:
        if X.shape[1] > selected_feature_indices.max():
            X = X[:, selected_feature_indices]
        else:
            raise ValueError(f"Feature vector too short ({X.shape[1]}) for selected indices")

    expected_dim = getattr(model, "expected_input_dim", expected_input_dim)
    if expected_dim is not None:
        if X.shape[1] > expected_dim:
            X = X[:, :expected_dim]
        elif X.shape[1] < expected_dim:
            X = np.pad(X, ((0, 0), (0, expected_dim - X.shape[1])), mode="constant")

    return X


def scan_file(file_path, auto_quarantine=True, excluded_roots=None):
    extractor = get_extractor()   #
    
    if is_excluded(file_path, excluded_roots):
        return {
            "result": "EXCLUDED",
            "probability": None,
            "file_path": file_path
        }

    

    # No hash match: existing PE/Random Forest pipeline
    # continues below.
    try:
        kind, header, file_size = classify_file(file_path)

        if kind == "error":
            return {
                "result": "ERROR",
                "probability": None,
                "file_path": file_path
            }

        # CRITICAL: Stop all analysis for non-PE files.
        if kind != "pe":
            return {
                "result": "SKIPPED",
                "probability": None,
                "file_path": file_path
            }


        if file_size > 500 * 1024 * 1024:
            return {
                "result": "TOO_LARGE",
                "probability": None,
                "file_path": file_path
            }

        
        # Skip very large files (optional, adjust limit as needed)
        if file_size > 500 * 1024 * 1024:  # 500MB limit
            return {"result": "CLEAN", "probability": 0, "file_path": file_path}

        # kind == "pe" — only now do we read the full file
        if file_size <= HEADER_PEEK_SIZE:
            # header IS the whole file — no need to reopen
            file_bytes = header
        else:
            try:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
            except Exception as e:
                return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}

                # SHA-256: reuse bytes already loaded for ML.
        # Skip hashing when the signature database is empty.
        known_hashes = load_malware_hashes()

        if known_hashes:
            digest = hashlib.sha256(file_bytes).hexdigest()

            if digest in known_hashes:
                add_log_entry(
                    file_path,
                    result="MALICIOUS",
                    details=f"Known SHA-256: {digest}"
                )

                DETECTED_MALWARE.append(file_path)

                quarantine_status = None

                if auto_quarantine:
                    quarantine_status = quarantine_file(file_path)

                return {
                    "result": "MALICIOUS",
                    "probability": None,
                    "file_path": file_path,
                    "category": "Known Malware Signature",
                    "detection_method": "SHA256_SIGNATURE",
                    "sha256": digest,
                    "signature_match": True,
                    "quarantine_status": quarantine_status,
                }

        # Existing save_pe_statistics() and feature
        # extraction continue below.


        def save_pe_statistics(verdict, probability=None, category=None):
            try:
                return record_pe_statistics(
                    file_path=file_path,
                    verdict=verdict,
                    probability=probability,
                    category=category,
                    file_bytes=file_bytes,
                )
            except Exception as stats_error:
                print(
                    f"[PE statistics] Could not save analysis for "
                    f"{file_path}: {stats_error}"
                )
                return None

        try:
            features = extractor.feature_vector(file_bytes)
        except Exception as e:
            # It had 'MZ' but failed extraction - still log it as ERROR but not spam
            add_log_entry(file_path, result="ERROR", details=f"PE extraction failed: {str(e)[:50]}")
            stats = save_pe_statistics("ERROR")
            return {
                "result": "ERROR",
                "probability": 0,
                "file_path": file_path,
                "details": str(e),
                "pe_statistics": stats,
            }
        
        # Check if model is available
        if model is None:
            add_log_entry(file_path, result="UNKNOWN", details="Model not loaded")
            stats = save_pe_statistics("UNKNOWN")
            return {
                "result": "UNKNOWN",
                "probability": 0,
                "file_path": file_path,
                "details": "Model not available",
                "pe_statistics": stats,
            }
        
        try:
            raw_features = np.asarray(
                features,
                dtype=np.float32
            ).reshape(1, -1)

            # Prepare features for the malware/benign model only.
            X = _prepare_model_features(raw_features)
        except ValueError as e:
            add_log_entry(file_path, result="ERROR", details=str(e))
            stats = save_pe_statistics("ERROR")
            return {"result": "ERROR", "probability": 0, "file_path": file_path,
                    "details": "Feature schema mismatch — extractor/model version drift",
                    "pe_statistics": stats}

        if X.shape[1] != getattr(model, "expected_input_dim", expected_input_dim or X.shape[1]):
            add_log_entry(file_path, result="ERROR", details=f"Feature vector shape mismatch ({X.shape[1]})")
            stats = save_pe_statistics("ERROR")
            return {"result": "ERROR", "probability": 0, "file_path": file_path,
                    "details": "Feature schema mismatch — extractor/model version drift",
                    "pe_statistics": stats}

        # Predict malware probability
        try:
            prob = float(model.predict_proba(X)[0][1])
            prediction = 1.0 if prob >= 0.5 else 0.0
        except Exception as e:
            add_log_entry(file_path, result="ERROR", details=f"Prediction failed: {e}")
            stats = save_pe_statistics("ERROR")
            return {
                "result": "ERROR",
                "probability": 0,
                "file_path": file_path,
                "details": str(e),
                "pe_statistics": stats,
            }

        behavior_probability = 0.0
        behavior_result = "NOT_EVALUATED"
        behavior_types = []
        behavior_type = None

        # Only evaluate behavior when malware is detected.
        if prediction == 1:
            try:
                # Use ORIGINAL EMBER features.
                # This function applies the behavior model's
                # own selected feature indices.
                behavior_summary = get_behavior_prediction_summary(
                    raw_features
                )

                # Reuse the SAME prediction result.
                behavior_probability = float(
                    behavior_summary.get("mean_probability", 0.0)
                )

                behavior_types = behavior_summary.get(
                    "predicted_labels", []
                )

                behavior_type = behavior_summary.get("top_label")

                # Classify whether any behavior label passed
                # its own configured threshold.
                behavior_result = (
                    "BEHAVIORAL_ANOMALY"
                    if behavior_types
                    else "NO_BEHAVIOR_LABEL_PREDICTED"
                )

            except Exception as e:
                print(
                    f"Behavior model evaluation failed "
                    f"for {file_path}: {e}"
                )

                behavior_probability = 0.0
                behavior_result = "BEHAVIOR_ERROR"
                behavior_types = []
                behavior_type = None


        category = categorize_threat(prob)
        stats = save_pe_statistics(
            "MALICIOUS" if prediction == 1 else "CLEAN",
            probability=prob,
            category=category,
        )

        # Generate XAI explanation asynchronously (without blocking scan)
        result_str = (
            "MALICIOUS"
            if prediction == 1
            else "CLEAN"
        )

        xai_report = None
        detection_id = None
        xai_job_id = None

        if result_str == "MALICIOUS":
            # Every detection gets an independent identifier.
            detection_id = new_detection_id()

            if not auto_quarantine:
                try:
                    xai_job_id = schedule_xai(
                        file_path=file_path,
                        features=features,
                        probability=prob,
                        result=result_str,
                        detection_id=detection_id
                    )

                except Exception as e:
                    print(
                        f"[XAI] Scheduling failed: {e}"
                    )

        if prediction == 1:
            DETECTED_MALWARE.append(file_path)
            details = (
                f"Category: {category}; behavior_probability={behavior_probability:.3f}; "
                f"behavior_result={behavior_result}; behavior_types={','.join(behavior_types) if behavior_types else 'unknown'}"
            )
            add_log_entry(
                file_path,
                result="MALICIOUS",
                probability=prob,
                details=details,
                behavior_confidence=behavior_probability,
                behavior_type=behavior_type,
                behavior_types=behavior_types,
                behavior_result=behavior_result,
            )

            try:
                enqueue_threat_notification(file_path, "MALICIOUS", prob, category)
            except Exception:
                pass

            if auto_quarantine:
                if prediction == 1:
                    if auto_quarantine:
                        quarantine_result = quarantine_file(file_path)
            return {
                "result": "MALICIOUS",
                "probability": prob,
                "file_path": file_path,
                "category": category,
                "behavior_probability": behavior_probability,
                "behavior_confidence": behavior_probability,
                "behavior_result": behavior_result,
                "behavior_types": behavior_types,
                "behavior_type": behavior_type,
                "behavior_model_metrics": get_behavior_model_metrics(),
                "detection_id": detection_id,
                "xai_job_id": xai_job_id,
                "xai_report": xai_report,
                "pe_statistics": stats,
            }
        else:
            # Clean results don't need file_bytes or features
            return {
                "result": "CLEAN",
                "probability": prob,
                "file_path": file_path,
                "behavior_probability": behavior_probability,
                "behavior_confidence": behavior_probability,
                "behavior_result": behavior_result,
                "behavior_types": behavior_types,
                "behavior_type": behavior_type,
                "behavior_model_metrics": get_behavior_model_metrics(), 
                "xai_report": xai_report,
                "pe_statistics": stats,
            }
    except Exception as e:
        print(f"Unexpected error scanning {file_path}: {e}")
        return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}
    #     # Send Telegram notification
    #     message = (
    #         f"[!] Malware Detected!\n"
    #         f"File: {os.path.basename(file_path)}\n"
    #         f"Path: {file_path}\n"
    #         f"Probability: {prob:.2%}\n"
    #         f"Severity: {category}"
    #     )
    #     send_telegram_notification(message)
        
    #     if auto_quarantine:
    #         if prob >= 0.90:
    #             print("Before quarantine, exists:", os.path.exists(file_path))
    #             quarantine_file(file_path)
    #             print("After quarantine, exists:", os.path.exists(file_path))
    #         else:
    #             allow_threat(file_path, category, "MALICIOUS")
    #     return {"result": "MALICIOUS", "probability": prob, "file_path": file_path, "category": category, "xai_report": xai_report, "file_bytes": file_bytes, "features": features}
    # else:
    #     # Only log clean files if they have a high enough probability of being malware
    #     return {"result": "CLEAN", "probability": prob, "file_path": file_path, "xai_report": xai_report, "file_bytes": file_bytes, "features": features}
    
def scan_text(file_path, auto_quarantine=True, excluded_roots=None):
    if is_excluded(file_path, excluded_roots):
        return {"result": "EXCLUDED", "probability": 0, "file_path": file_path}
        
    try:
        # SINGLE I/O CYCLE: Read entire small script into memory
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        content = file_bytes.decode("utf-8", errors="ignore").lower()
    except Exception as e:
        return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}

    found_keywords = [kw for kw in SUS_WRODS if kw in content]
    result_str = "SUSPICIOUS" if found_keywords else "CLEAN"
    xai_report = None
    
    if found_keywords:
        # Run XAI analysis asynchronously for scripts too!
        if found_keywords:
            schedule_xai(
                file_path=file_path,
                features=[],
                probability=0.7,
                result=result_str
            )

            xai_report = None
            
        DETECTED_SUSPICIOUS.append(file_path)
        add_log_entry(file_path, "SUSPICIOUS", details=f"Keywords: {', '.join(found_keywords)}")

        try:
            enqueue_threat_notification(file_path, "SUSPICIOUS", 0.7, "Script/Keyword")
        except Exception:
            pass

        if auto_quarantine:
            try:
                quarantine_file(file_path)
            except Exception:
                pass

        return {"result": "SUSPICIOUS", "probability": 0.7, "file_path": file_path, "keywords": found_keywords, "xai_report": xai_report}
        
    return {"result": "CLEAN", "probability": 0, "file_path": file_path, "xai_report": xai_report}