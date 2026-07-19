import os
import numpy as np
import threading
from system.config import HEADER_PEEK_SIZE, KNOWN_SCRIPT_EXTS, KNOWN_SKIP_EXTS, DETECTED_MALWARE, DETECTED_SUSPICIOUS, SUS_WRODS
from system.security.exclusions import is_excluded
from system.security.allowed import allow_threat
from system.scanner.extractor import get_extractor
from system.history.logs import add_log_entry
from system.model_load import model, selected_feature_indices, expected_input_dim
from system.quarantines.quarantine import quarantine_file
from system.utils.utility import categorize_threat
from system.notifications import send_telegram_notification
from system.xai.engine import xai_engine

def classify_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    try:
        file_size = os.path.getsize(file_path)
    except Exception:
        return ("error", None, 0)

    if ext in KNOWN_SKIP_EXTS:
        return ("skip", None, file_size)   # no open(), no read() at all

    try:
        with open(file_path, "rb") as f:
            header = f.read(HEADER_PEEK_SIZE)
    except Exception:
        return ("error", None, 0)

    if header[:2] == b'MZ':
        return ("pe", header, file_size)

    return ("skip", None, file_size)

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
        return {"result": "EXCLUDED", "probability": 0, "file_path": file_path}
    
    try:
        # First check if it's a PE file
        kind, header, file_size = classify_file(file_path)

        if kind == "error":
            return {"result": "ERROR", "probability": 0, "file_path": file_path}
        if kind == "skip":
            return {"result": "CLEAN", "probability": 0, "file_path": file_path}
        
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
        try:
            features = extractor.feature_vector(file_bytes)
        except Exception as e:
            # It had 'MZ' but failed extraction - still log it as ERROR but not spam
            add_log_entry(file_path, result="ERROR", details=f"PE extraction failed: {str(e)[:50]}")
            return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}
        
        # Check if model is available
        if model is None:
            add_log_entry(file_path, result="UNKNOWN", details="Model not loaded")
            return {"result": "UNKNOWN", "probability": 0, "file_path": file_path, "details": "Model not available"}
        
        try:
            X = _prepare_model_features(features)
        except ValueError as e:
            add_log_entry(file_path, result="ERROR", details=str(e))
            return {"result": "ERROR", "probability": 0, "file_path": file_path,
                    "details": "Feature schema mismatch — extractor/model version drift"}

        if X.shape[1] != getattr(model, "expected_input_dim", expected_input_dim or X.shape[1]):
            add_log_entry(file_path, result="ERROR", details=f"Feature vector shape mismatch ({X.shape[1]})")
            return {"result": "ERROR", "probability": 0, "file_path": file_path,
                    "details": "Feature schema mismatch — extractor/model version drift"}

        # Predict malware probability
        try:
            prob = float(model.predict_proba(X)[0][1])
            prediction = 1.0 if prob >= 0.5 else 0.0
        except Exception as e:
            add_log_entry(file_path, result="ERROR", details=f"Prediction failed: {e}")
            return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}
        
        category = categorize_threat(prob)

        # Generate XAI explanation asynchronously (without blocking scan)
        result_str = "MALICIOUS" if prediction == 1 else "CLEAN"
        xai_report = None
        
        # We'll store xai_report later if needed, but for now, run analysis in background
        if result_str == "MALICIOUS":
            def _run_xai():
                try:
                    # Make a copy of file_bytes in case it's garbage collected
                    file_bytes_copy = file_bytes
                    xai_engine.analyze_file(file_path, file_bytes_copy, features, prob, result_str)
                except Exception as xai_error:
                    print(f"XAI analysis failed: {xai_error}")
            threading.Thread(target=_run_xai, daemon=True).start()

        if prediction == 1:
            DETECTED_MALWARE.append(file_path)
            add_log_entry(file_path, result="MALICIOUS", probability=prob, details=f"Category: {category}")
            
            # Send Telegram notification
            message = (
                f"[!] Malware Detected!\n"
                f"File: {os.path.basename(file_path)}\n"
                f"Path: {file_path}\n"
                f"Probability: {prob:.2%}\n"
                f"Severity: {category}"
            )
            send_telegram_notification(message)
            
            if auto_quarantine:
                if prob >= 0.90:
                    quarantine_file(file_path)
                else:
                    allow_threat(file_path, category, "MALICIOUS")
            # Don't include file_bytes or features in result dict to save memory
            return {"result": "MALICIOUS", "probability": prob, "file_path": file_path, "category": category, "xai_report": xai_report}
        else:
            # Clean results don't need file_bytes or features
            return {"result": "CLEAN", "probability": prob, "file_path": file_path, "xai_report": xai_report}
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
        def _run_xai_script():
            try:
                file_bytes_copy = file_bytes
                xai_engine.analyze_file(file_path, file_bytes_copy, [], 0.7, result_str)
            except Exception as xai_error:
                print(f"XAI analysis failed for script: {xai_error}")
        threading.Thread(target=_run_xai_script, daemon=True).start()
        xai_report = None  # We'll generate it on demand if user clicks "Explain"
            
        DETECTED_SUSPICIOUS.append(file_path)
        add_log_entry(file_path, "SUSPICIOUS", details=f"Keywords: {', '.join(found_keywords)}")
        
        # Performance Hint: Push Telegram notifications into an asynchronous background queue 
        # or thread instead of executing them synchronously inside the critical pathway here.
        message = (
            f"[!] Suspicious File Detected!\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Path: {file_path}\n"
            f"Reason: Contains suspicious keyword(s): {', '.join(found_keywords)}"
        )
        send_telegram_notification(message)
        
        if auto_quarantine:
            # Quarantine suspicious script files instead of allowing them
            print("Before quarantine, exists:", os.path.exists(file_path))
            quarantine_file(file_path)
            print("After quarantine, exists:", os.path.exists(file_path))
        
        return {"result": "SUSPICIOUS", "probability": 0.7, "file_path": file_path, "keywords": found_keywords, "xai_report": xai_report}
        
    return {"result": "CLEAN", "probability": 0, "file_path": file_path, "xai_report": xai_report}