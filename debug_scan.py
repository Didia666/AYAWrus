
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system.cli import scan_file, display_xai_explanation

test_file = r"d:\SUMMER\AYAWrus_10_07_26\test_suspicious.ps1"
print(f"Scanning file: {test_file}")
result = scan_file(test_file, auto_quarantine=False)
print("Scan Result:", result)
if "xai_report" in result:
    print("\nXAI Report found!")
    display_xai_explanation(result["xai_report"])
else:
    print("\nXAI Report NOT found!")

