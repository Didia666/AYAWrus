
# ===========================================
# CATEGORIZING
# ===========================================

from system.config import (
    MALWARE_MALICIOUS_THRESHOLD,
    MALWARE_SUSPICIOUS_THRESHOLD,
)


def classify_malware_probability(prob):
    if prob >= MALWARE_MALICIOUS_THRESHOLD:
        return "MALICIOUS"
    if prob >= MALWARE_SUSPICIOUS_THRESHOLD:
        return "SUSPICIOUS"
    return "CLEAN"


def categorize_threat(prob):
    if prob >= MALWARE_MALICIOUS_THRESHOLD:
        return "SEVERE"
    elif prob >= 0.70:
        return "HIGH"
    elif prob >= 0.40:
        return "MEDIUM"
    elif prob >= 0.20:
        return "LOW"
    else:
        return "CLEAN"

    
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