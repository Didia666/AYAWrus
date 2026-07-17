import os
import magic
import numpy as np
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
        with open(file_path, "rb") as f:
            header = f.read(HEADER_PEEK_SIZE)
    except Exception:
        return ("error", None, 0)

    if header[:2] == b'MZ':
        return ("pe", header, file_size)
    if ext in KNOWN_SKIP_EXTS:
        return ("skip", None, file_size)          # no magic() call needed
    if ext in KNOWN_SCRIPT_EXTS:
        return ("script", header, file_size)      # no magic() call needed

    try:
        magic_instance = magic.Magic(mime=True)
        mime = magic_instance.from_buffer(header)
    except Exception as e:
        print(f"Magic failed: {e}")
        mime = ""
    script_mimes = (
        "text/x-shellscript", "text/x-python", "text/x-perl",
        "text/plain", "text/x-msdos-batch",
    )
    if mime.startswith("text/") and mime in script_mimes:
        return ("script", header, file_size)

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
    
    # First check if it's a PE file
    kind, header, file_size = classify_file(file_path)

    if kind == "error":
        return {"result": "ERROR", "probability": 0, "file_path": file_path}
    if kind == "skip":
        return {"result": "CLEAN", "probability": 0, "file_path": file_path}
    if kind == "script":
        return scan_text(file_path, auto_quarantine, excluded_roots)

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
        prediction = float(model.predict(X)[0]) 
    except Exception as e:
        add_log_entry(file_path, result="ERROR", details=f"Prediction failed: {e}")
        return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}
    
    category = categorize_threat(prob)

    # Generate XAI explanation (without modifying core detection logic)
    result_str = "MALICIOUS" if prediction == 1 else "CLEAN"
    xai_report = None
    if result_str == "MALICIOUS":
        try:
            xai_report = xai_engine.analyze_file(file_path, file_bytes, features, prob, result_str)
        except Exception as xai_error:
            print(f"XAI analysis failed: {xai_error}")

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
        return {"result": "MALICIOUS", "probability": prob, "file_path": file_path, "category": category, "xai_report": xai_report, "file_bytes": file_bytes, "features": features}
    else:
        # Only log clean files if they have a high enough probability of being malware
        return {"result": "CLEAN", "probability": prob, "file_path": file_path, "xai_report": xai_report, "file_bytes": file_bytes, "features": features}
    
def scan_text(file_path, auto_quarantine=True, excluded_roots=None):
    if is_excluded(file_path, excluded_roots):
        return {"result": "EXCLUDED", "probability": 0, "file_path": file_path}
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        with open(file_path, "r", errors="ignore") as f:
            content = f.read().lower()
    except Exception as e:
        return {"result": "ERROR", "probability": 0, "file_path": file_path, "details": str(e)}

    found_keywords = []
    for keyword in SUS_WRODS:
        if keyword in content:
            found_keywords.append(keyword)
    
    # Generate XAI explanation (for script files)
    result_str = "SUSPICIOUS" if found_keywords else "CLEAN"
    xai_report = None
    if found_keywords:
        try:
            xai_report = xai_engine.analyze_file(file_path, file_bytes, [], 0.7, result_str)
        except Exception as xai_error:
            print(f"XAI analysis failed for script: {xai_error}")
    
    if found_keywords:
        DETECTED_SUSPICIOUS.append(file_path)
        add_log_entry(file_path, "SUSPICIOUS", details=f"Keywords: {', '.join(found_keywords)}")
        
        # Send Telegram notification
        message = (
            f"[!] Suspicious File Detected!\n"
            f"File: {os.path.basename(file_path)}\n"
            f"Path: {file_path}\n"
            f"Reason: Contains suspicious keyword(s): {', '.join(found_keywords)}"
        )
        send_telegram_notification(message)
        
        if auto_quarantine:
            # Quarantine suspicious script files instead of allowing them
            quarantine_file(file_path)
        
        return {"result": "SUSPICIOUS", "probability": 0.7, "file_path": file_path, "keywords": found_keywords, "xai_report": xai_report}
        
    # Don't log every safe file - just return the status
    return {"result": "CLEAN", "probability": 0, "file_path": file_path, "xai_report": xai_report}