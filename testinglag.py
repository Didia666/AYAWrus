import os
import shutil
import stat
import numpy as np
import json
import magic
import threading
from datetime import datetime
from model_load import model, selected_feature_indices
from thrember.features import PEFeatureExtractor
from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from concurrent.futures import ProcessPoolExecutor, as_completed

from config import *
from notifications.telegram import send_telegram_notification
from history.logs import add_log_entry, begin_log_buffer, flush_log_buffer, view_logs, load_log
from history.reports import generate_incident_report, list_incident_reports
from security.allowed import *
from security.exclusions import *

extractor = PEFeatureExtractor()   # one instance per batch, not per file



try:
    import onnxruntime as rt
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


# CURRENT_SCAN_LOG = {
#     "scan_type": "-",
#     "start_time": "-",
#     "end_time": "-",
#     "items_scanned": 0,
#     "threats_removed": 0,
#     "duration": "-",
#     "file": "No threats",
#     "threat_type": "-",
#     "score": "-",
#     "action": "None"
# }

# def update_scan_log(file, scanned, threats, threat_type="", score="", action=""):
#     CURRENT_SCAN_LOG.update({
#         "items_scanned": scanned,
#         "threats_removed": threats,
#         "file": file,
#         "threat_type": threat_type,
#         "score": score,
#         "action": action
#     })

# def load_log():
#     return [CURRENT_SCAN_LOG]

SUS_WRODS = [
    "powershell",
    "cmd.exe",
    "downloadstring",
    "base64",
    "invoke-webrequest",
    "start-process",
    "reg add",
    "taskkill",
]





CURRENT_SCAN_LOG = {
    "scan_type": "Quick",
    "start_time": "-",
    "end_time": "-",
    "items_scanned": 0,
    "threats_removed": 0,
    "duration": "-",
    "file": "",
    "threat_type": "",
    "score": "",
    "action": ""
}

def update_scan_log(file, scanned, threats, threat_type="", score="", action=""):
    CURRENT_SCAN_LOG.update({
        "items_scanned": scanned,
        "threats_removed": threats,
        "file": file,
        "threat_type": threat_type,
        "score": score,
        "action": action
    })

    
# Configuration file for Telegram bot
CONFIG_FILE = "config.json"


#History




    


def normalize_user_path(path: str) -> str:
    try:
        if not isinstance(path, str):
            return path
        p = os.path.abspath(path)
        parts = p.split(os.sep)
        # Windows: C:\Users\<name>\...
        if len(parts) > 3 and parts[1].lower() == "users":
            cur = os.path.basename(current_user_profile())
            if parts[2].lower() != cur.lower():
                candidate = os.sep.join([parts[0], parts[1], cur] + parts[3:])
                if os.path.exists(candidate):
                    return candidate
        return path
    except Exception:
        return path

#Threat Categorization
def categorize_threat(prob):
    if prob >= 0.90:
        return "SEVERE"
    elif prob >= 0.70:
        return "HIGH"
    elif prob >= 0.40:
        return "MEDIUM"
    elif prob >= 0.20:
        return "LOW"
    else:
        return "CLEAN"
    
#Scanning

def custom_scan(path):
    begin_log_buffer()
    try: 
        if os.path.isfile(path):
            print("Custom scan (single file)")
            scan_result = scan_file(path)
            print(scan_result)
            if "xai_report" in scan_result and scan_result["xai_report"]:
                display_xai_explanation(scan_result["xai_report"])

        elif os.path.isdir(path):
            print("Custom scan (folder)")
            scan_folder_parallel(path)

        else:
            print("Invalid path. File/Folder does not exist.")
    finally:
        flush_log_buffer()


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
        futures = [pool.submit(_extract_worker_batch, chunk, HEADER_PEEK_SIZE) for chunk in chunks]
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

# def is_pe_file(file_bytes):
#     """Check if the file is a valid PE file"""
#     # PE files start with 'MZ' (0x5A4D)
#     return len(file_bytes) >= 2 and file_bytes[:2] == b'MZ'


# def is_pe_file(file_path):
#     try:
#         with open(file_path, "rb") as f:
#             header = f.read(64)
    
#         if len(header) < 2 or header[:2] != b'MZ':
#             return False
        
#         pe_offset = int.from_bytes(header[0x3C:0x40], byteorder='little')
#         with open(file_path, "rb") as f:
#             f.seek(pe_offset)
#             pe_header = f.read(4)
            
#         if pe_header != b'PE\x00\x00':
#             return False

    
#         try:
#             file_type = magic.from_file(file_path)
#             return ("PE32" in file_type or "executable" in file_type)
#         except Exception:
#             return True  # magic unavailable/failed — trust the MZ+PE header check
#     except Exception:
#         return False

HEADER_PEEK_SIZE = 4096  # enough for magic to fingerprint almost anything
KNOWN_SKIP_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".pdf", ".zip",
                   ".dll", ".sys", ".ttf", ".woff", ".ico", ".avi", ".mkv", ".wav"}
KNOWN_SCRIPT_EXTS = {".ps1", ".bat", ".cmd", ".vbs", ".py", ".sh"}

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

def scan_file(file_path, auto_quarantine=True, excluded_roots=None):
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
    
    # Convert to numpy array
    X = np.array(features).reshape(1, -1)
    if selected_feature_indices is not None:
        if X.shape[1] > selected_feature_indices.max():
            X = X[:, selected_feature_indices]
        else:
            add_log_entry(file_path, result="ERROR",
                        details=f"Feature vector too short ({X.shape[1]}) for selected indices")
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

def regular_scan():
    print("=== Running Regular System Scan ===")
    begin_log_buffer()  # Start buffering log entries
    try:
        for directory in REGULAR_SCAN_DIRS:
            if os.path.exists(directory):
                print(f"\nScanning: {directory}")
                scan_folder_parallel(directory)  # use parallel version
            else:
                print(f"Skipping missing folder: {directory}")
    finally:
        flush_log_buffer()  # Write all buffered log entries at once


def quick_scan():
    print("=== QUICK SCAN ===")
    begin_log_buffer()
    try:
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
            for folder in QUICK_SCAN_DIRS:
                if os.path.exists(folder):
                    scan_folder_parallel(folder, pool=pool)
    finally:
        flush_log_buffer()



# Running    
if __name__ == "__main__":
    mode = input("Choose scan mode: "
             "(1) Regular Scan  "
             "(2) Quick Scan  "
             "(3) Custom Scan  "
             "(4) View Logs  "
             "(5) Generate Incident Report\n> ")


    if mode == "1":
        regular_scan()
        # activity_feed._rebuild_activity_feed()
        process_quarantine()

    elif mode == "2":
        quick_scan()
        # activity_feed._rebuild_activity_feed()

    elif mode == "3":   
        user_path = input("Enter file or folder path: ")
        custom_scan(user_path)
        # activity_feed._rebuild_activity_feed()
        process_quarantine()

    elif mode == "4":
        view_logs()

    elif mode == "5":
        generate_incident_report()

    else:
        print("Invalid option.")










def get_last_log_entry(file_path: str):
    try:
        log = load_log()
        for e in reversed(log):
            if e.get("file_path") == file_path:
                return e
    except Exception:
        pass
    return None



# ==============================================
# EXPLAINABLE AI (XAI) EXPLANATION ENGINE
# ==============================================

class XAIExplanationEngine:
    """
    Explainable AI Engine for Malware Detection System
    Generates human-readable explanations of scan results
    """
    
    # Educational topics for "Learn Why" section
    EDUCATIONAL_TOPICS = {
        "pe_files": {
            "title": "What are PE Files?",
            "content": """
PE stands for Portable Executable. It's the standard file format for Windows executables (.exe),
DLLs (.dll), and other system files. PE files contain headers, sections (like code, data, resources),
and information about how the file should be loaded into memory. Malware often modifies PE structures
to avoid detection or make analysis harder.
            """
        },
        "entropy": {
            "title": "What is File Entropy?",
            "content": """
Entropy measures how random or disordered data is. Regular files (like text or images) have low entropy.
Encrypted or compressed files have very high entropy (around 7.0-8.0). Malware often uses encryption
or packing to hide its code, which increases entropy and makes detection harder.
            """
        },
        "imported_apis": {
            "title": "What are Imported APIs?",
            "content": """
APIs (Application Programming Interfaces) are functions that programs use to interact with the operating
system. Malware often uses suspicious APIs like CreateRemoteThread (for code injection), VirtualAlloc
(for memory manipulation), or WinExec (for executing commands). Checking imported APIs helps identify
potentially malicious behavior.
            """
        },
        "feature_extraction": {
            "title": "How Feature Extraction Works",
            "content": """
Feature extraction converts a file into numerical values that a machine learning model can understand.
For malware detection, features include things like file size, entropy, imported APIs, section information,
and more. The EMBER dataset is a common source of these features.
            """
        },
        "random_forest": {
            "title": "What is a Random Forest?",
            "content": """
Random Forest is a machine learning algorithm that uses many decision trees working together. Each tree
makes a prediction, and the forest combines these predictions for the final result. Random Forests are
good at detecting malware because they can handle complex patterns in data and are less prone to overfitting.
            """
        },
        "confidence_score": {
            "title": "Understanding Confidence Scores",
            "content": """
The confidence score (0-100%) tells you how sure the model is of its prediction. A score of 95% means the
model is 95% confident the file is malware. However, high confidence doesn't always mean it's actually
malware - there can still be false positives!
            """
        },
        "false_positives": {
            "title": "What are False Positives?",
            "content": """
A false positive is when a safe file is incorrectly labeled as malware. No malware detector is perfect!
That's why it's important to review detections before taking action, and why we recommend quarantine
instead of immediate deletion.
            """
        },
        "quarantine": {
            "title": "Why Quarantine Instead of Delete?",
            "content": """
Quarantine moves suspicious files to a secure, isolated location instead of deleting them immediately.
This is safer because:
1. You can restore files if they were false positives
2. You can analyze quarantined files later
3. You avoid accidental data loss
Always quarantine first, then review!
            """
        }
    }
    
    # List of suspicious API functions
    SUSPICIOUS_APIS = {
        "CreateRemoteThread", "CreateRemoteThreadEx", "VirtualAlloc", "VirtualAllocEx",
        "VirtualProtect", "VirtualProtectEx", "WriteProcessMemory", "ReadProcessMemory",
        "OpenProcess", "TerminateProcess", "WinExec", "ShellExecute", "ShellExecuteEx",
        "CreateProcess", "CreateProcessAsUser", "CreateProcessWithLogonW", "LoadLibrary",
        "LoadLibraryEx", "GetProcAddress", "CreateFile", "CreateFileMapping", "MapViewOfFile",
        "RegOpenKey", "RegOpenKeyEx", "RegSetValue", "RegSetValueEx", "InternetOpen",
        "InternetOpenUrl", "InternetReadFile", "InternetWriteFile"
    }
    
    def __init__(self):
        self.scan_steps = []
        self.suspicious_characteristics = []
    
    def analyze_file(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        """
        Analyze a scanned file and generate a complete explanation
        """
        self.scan_steps = []
        self.suspicious_characteristics = []
        
        # Step 1: Verify file type
        self._add_scan_step("Verifying file type...", "Checking if file is a valid PE file")
        
        # Step 2: Analyze PE structure
        self._add_scan_step("Analyzing PE structure...", "Extracting PE headers and sections")
        
        # Step 3: Calculate entropy
        self._add_scan_step("Calculating file entropy...", "Measuring randomness in file data")
        
        # Step 4: Inspect imported APIs
        self._add_scan_step("Inspecting imported APIs...", "Checking for suspicious function imports")
        
        # Step 5: Extract features
        self._add_scan_step("Extracting features...", "Converting file to numerical feature vector")
        
        # Step 6: Run Random Forest model
        self._add_scan_step("Running Random Forest model...", "Classifying file using machine learning")
        
        # Step 7: Generate final prediction
        self._add_scan_step("Generating prediction...", "Finalizing scan results")
        
        # Analyze characteristics
        self._analyze_characteristics(file_path, file_bytes, features, probability, result)
        
        return self._generate_explanation_report(file_path, probability, result)
    
    def _add_scan_step(self, title: str, description: str):
        """Add a step to the scan process simulation"""
        self.scan_steps.append({
            "title": title,
            "description": description
        })
    
    def _analyze_characteristics(self, file_path: str, file_bytes: bytes, features: list, probability: float, result: str):
        """Analyze the file's characteristics and identify suspicious elements"""
        # Calculate entropy (simple version)
        entropy = self._calculate_entropy(file_bytes)
        if entropy > 7.0:
            self.suspicious_characteristics.append({
                "type": "high_entropy",
                "title": "High Entropy Detected",
                "description": f"File entropy: {entropy:.2f}. This may indicate encryption or packing commonly used by malware."
            })
        
        # Analyze PE file (if possible)
        try:
            import pefile
            pe = pefile.PE(data=file_bytes)
            
            # Check section entropy
            high_entropy_sections = []
            for section in pe.sections:
                section_entropy = section.get_entropy()
                if section_entropy > 7.0:
                    high_entropy_sections.append(f"{section.Name.decode('utf-8', errors='ignore').strip()} ({section_entropy:.2f})")
            if high_entropy_sections:
                self.suspicious_characteristics.append({
                    "type": "high_entropy_sections",
                    "title": "High Entropy in Sections",
                    "description": f"Suspicious sections with high entropy: {', '.join(high_entropy_sections)}. Packed or encrypted code often has high entropy."
                })
            
            # Check imported APIs
            suspicious_imports = []
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    for imp in entry.imports:
                        if imp.name:
                            imp_name = imp.name.decode('utf-8', errors='ignore')
                            for suspicious_api in self.SUSPICIOUS_APIS:
                                if suspicious_api.lower() in imp_name.lower():
                                    suspicious_imports.append(imp_name)
                                    break
            if suspicious_imports:
                unique_imports = list(set(suspicious_imports))[:5]
                self.suspicious_characteristics.append({
                    "type": "suspicious_imports",
                    "title": "Suspicious API Imports",
                    "description": f"Detected potentially malicious APIs: {', '.join(unique_imports)}. These functions are commonly used by malware for injection, process manipulation, or network activity."
                })
            
            pe.close()
        except Exception as e:
            pass
        
        # Check probability/confidence
        confidence = probability * 100
        if result == "MALICIOUS":
            risk_level = self._get_risk_level(probability)
            self.suspicious_characteristics.append({
                "type": "malicious_prediction",
                "title": "Malicious Prediction",
                "description": f"Model classified this file as malicious with {confidence:.1f}% confidence (Risk Level: {risk_level})."
            })
        elif result == "SUSPICIOUS":
            self.suspicious_characteristics.append({
                "type": "suspicious_prediction",
                "title": "Suspicious Prediction",
                "description": "File contains suspicious indicators."
            })
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of file data"""
        if not data:
            return 0.0
        
        from collections import Counter
        import math
        byte_counts = Counter(data)
        entropy = 0.0
        length = len(data)
        
        for count in byte_counts.values():
            p = count / length
            entropy -= p * math.log2(p)
        
        return entropy
    
    def _get_risk_level(self, probability: float) -> str:
        """Get risk level based on probability"""
        if probability >= 0.90:
            return "SEVERE"
        elif probability >= 0.70:
            return "HIGH"
        elif probability >= 0.40:
            return "MEDIUM"
        elif probability >= 0.20:
            return "LOW"
        else:
            return "CLEAN"
    
    def _generate_explanation_report(self, file_path: str, probability: float, result: str) -> dict:
        """Generate the complete explanation report"""
        confidence = probability * 100
        risk_level = self._get_risk_level(probability)
        
        # Build the detailed explanation
        explanation_parts = []
        
        if result == "MALICIOUS":
            explanation_parts.append(f"The Random Forest model identified this file as malicious with {confidence:.1f}% confidence.")
        elif result == "SUSPICIOUS":
            explanation_parts.append("This file contains suspicious characteristics that warrant further investigation.")
        else:
            explanation_parts.append("The model determined this file is likely safe.")
        
        for char in self.suspicious_characteristics:
            explanation_parts.append(char["description"])
        
        if result in ("MALICIOUS", "SUSPICIOUS"):
            explanation_parts.append("Remember: No detection system is perfect. Review carefully before taking action.")
        
        # Generate action recommendations
        recommendations = self._get_action_recommendations(result, probability, risk_level)
        
        return {
            "prediction": "Malicious" if result == "MALICIOUS" else "Suspicious" if result == "SUSPICIOUS" else "Safe",
            "confidence": confidence,
            "risk_level": risk_level,
            "scan_steps": self.scan_steps,
            "suspicious_characteristics": self.suspicious_characteristics,
            "explanation": "\n\n".join(explanation_parts),
            "recommendations": recommendations,
            "educational_topics": self.EDUCATIONAL_TOPICS
        }
    
    def _get_action_recommendations(self, result: str, probability: float, risk_level: str) -> list:
        """Get recommended actions based on scan result"""
        recommendations = []
        
        if result == "MALICIOUS":
            if probability >= 0.90:
                recommendations.append("Quarantine the file immediately")
                recommendations.append("Do not execute the file")
            elif probability >= 0.70:
                recommendations.append("Quarantine the file")
                recommendations.append("Scan with another antivirus tool for confirmation")
            else:
                recommendations.append("Quarantine the file temporarily")
                recommendations.append("Review the file manually")
        elif result == "SUSPICIOUS":
            recommendations.append("Quarantine the file")
            recommendations.append("Review the suspicious indicators")
        else:
            recommendations.append("Keep the file")
            recommendations.append("Regularly update your antivirus definitions")
        
        return recommendations

# Global XAI engine instance
xai_engine = XAIExplanationEngine()

def display_xai_explanation(xai_report: dict):
    """
    Display the XAI explanation report in a human-readable format
    """
    if not xai_report:
        print("\nXAI explanation not available for this file.")
        return
    
    print("\n" + "="*80)
    print(" "*30 + "AI EXPLANATION PANEL")
    print("="*80)
    
    print(f"\nPrediction: {xai_report['prediction']}")
    print(f"Confidence: {xai_report['confidence']:.1f}%")
    print(f"Risk Level: {xai_report['risk_level']}")
    
    print("\n" + "-"*80)
    print("Scan Process Simulation:")
    print("-"*80)
    for i, step in enumerate(xai_report['scan_steps'], 1):
        print(f"  {i}. {step['title']}")
        print(f"     {step['description']}")
    
    if xai_report['suspicious_characteristics']:
        print("\n" + "-"*80)
        print("Detected Suspicious Characteristics:")
        print("-"*80)
        for char in xai_report['suspicious_characteristics']:
            print(f"  * {char['title']}")
            print(f"    {char['description']}")
    
    print("\n" + "-"*80)
    print("Detailed Explanation:")
    print("-"*80)
    print(xai_report['explanation'])
    
    print("\n" + "-"*80)
    print("Recommended Actions:")
    print("-"*80)
    for action in xai_report['recommendations']:
        print(f"  -> {action}")
    
    print("\n" + "-"*80)
    print("Learn Why:")
    print("-"*80)
    for topic_key, topic in xai_report['educational_topics'].items():
        print(f"\n{topic['title']}")
        print(f"{topic['content']}")
    
    print("\n" + "="*80)
