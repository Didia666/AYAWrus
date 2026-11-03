
from system.scanner.malware_impact_engine import (
    analyze_behavior_predictions
)

from system.scanner.scan_target_discovery import (
    discover_likely_targets
)

# Simulate output from your existing model.
# This does NOT train or execute another model.
behavior_summary = {
    "predicted_labels": [
        "ransom",
        "wiper"
    ],
    "label_scores": {
        "ransom": 0.82,
        "wiper": 0.76
    }
}

# STEP 1: Analyze behavior predictions.
impact = analyze_behavior_predictions(
    behavior_summary
)

print("\n=== IMPACT ANALYSIS ===")
print(impact)

# STEP 2: Discover potential target files.
result = discover_likely_targets(
    impact_result=impact,

    # Start with a small test folder.
    search_roots=[
        r"C:\Users\Karl\Documents"
    ],

    excluded_roots=[
        r"C:\Program Files\AYAWrus"
    ],

    max_files=1000,
    timeout=30
)

print("\n=== LIKELY TARGETS ===")
print("State:", result["state"])
print("Files scanned:", result["files_scanned"])
print("Matching files:", result["at_risk_count"])

for file in result["files"][:10]:
    print(
        file["category"],
        file["path"],
        file["reason"]
    )
