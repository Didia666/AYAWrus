import os
import time
from datetime import datetime
from history.logs import load_log
from notifications.telegram import send_telegram_notification
from quarantines.quarantine import list_quarantine_items

def generate_incident_report():
    log = load_log()

    # Filter only suspicious + malware
    filtered = [
        entry for entry in log
        if entry["result"] in ("MALICIOUS", "SUSPICIOUS")
    ]

    if not filtered:
        print("\nNo incidents found. The system is clean.")
        return

    # Create filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_name = f"incident_report_{timestamp}.txt"

    lines = []
    lines.append("=== INCIDENT REPORT ===")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"Total Incidents: {len(filtered)}")
    lines.append("")

    # Count types
    malware_count = sum(1 for x in filtered if x["result"] == "MALICIOUS")
    suspicious_count = sum(1 for x in filtered if x["result"] == "SUSPICIOUS")

    lines.append(f"Malware Files: {malware_count}")
    lines.append(f"Suspicious Files: {suspicious_count}")
    lines.append("\n-----------------------------\n")

    # Add each entry
    for entry in filtered:
        lines.append(f"Time: {entry['timestamp']}")
        lines.append(f"File: {entry['file_path']}")
        lines.append(f"Type: {entry['result']}")

        if entry.get("probability") is not None:
            lines.append(f"Probability: {entry['probability']:.4f}")

        if entry.get("details"):
            lines.append(f"Details: {entry['details']}")

        lines.append("\n-----------------------------\n")

    # Save the report
    with open(report_name, "w") as f:
        f.write("\n".join(lines))

    print(f"\nIncident report generated: {report_name}")

def list_incident_reports():
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        return [
            f for f in os.listdir(base)
            if f.startswith("incident_report_") and f.endswith(".txt")
        ]
    except Exception:
        return []
    
def generate_scan_report():
    """Generate a comprehensive scan report and return it as text"""
    log = load_log()
    threats = [e for e in log if e.get("result") in ("MALICIOUS", "SUSPICIOUS")]
    quarantine = list_quarantine_items()
    exclusions = list_exclusions()
    allowed = list_allowed_threats()
    
    report = []
    report.append("=" * 50)
    report.append("         MALWARE DETECTION SYSTEM SCAN REPORT")
    report.append("=" * 50)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append(f"Total Files Scanned: {len(log)}")
    report.append(f"Threats Found: {len(threats)}")
    report.append(f"Files in Quarantine: {len(quarantine)}")
    report.append(f"Allowed Threats: {len(allowed)}")
    report.append(f"Exclusions: {len(exclusions)}")
    report.append("")
    report.append("-" * 50)
    report.append("DETAILED THREAT LIST")
    report.append("-" * 50)
    
    if not threats:
        report.append("No threats found! System is clean!")
    else:
        for i, threat in enumerate(threats, 1):
            path = threat.get("file_path", "Unknown")
            result = threat.get("result", "Unknown")
            prob = threat.get("probability")
            details = threat.get("details", "")
            ts = threat.get("timestamp", "Unknown")
            
            report.append(f"\nThreat #{i}:")
            report.append(f"  File: {os.path.basename(path)}")
            report.append(f"  Path: {path}")
            report.append(f"  Type: {result}")
            if prob is not None:
                report.append(f"  Probability: {prob:.2%}")
            report.append(f"  Time: {ts}")
            if details:
                report.append(f"  Details: {details}")
    
    report.append("")
    report.append("=" * 50)
    report.append("         END OF REPORT")
    report.append("=" * 50)
    
    return "\n".join(report)

def send_scan_report():
    """Generate a scan report and send it to Telegram"""
    report = generate_scan_report()
    
    # Send the report in chunks if it's too long
    max_length = 4096  # Telegram message limit
    chunks = [report[i:i+max_length] for i in range(0, len(report), max_length)]
    
    for chunk in chunks:
        success = send_telegram_notification(chunk)
        if not success:
            return False
        time.sleep(0.5)  # Small delay between messages
    
    return True