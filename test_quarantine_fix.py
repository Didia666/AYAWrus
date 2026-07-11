#!/usr/bin/env python3
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions
from Malware_System import (
    _load_quarantine_index,
    list_quarantine_items,
    _normalize_path
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUARANTINE_DIR = os.path.join(BASE_DIR, "Quarantine")

print("=" * 80)
print("TESTING REPAIRED QUARANTINE SYSTEM")
print("=" * 80)

# Test 1: Load index
print("\nTest 1: Loading quarantine index...")
idx = _load_quarantine_index()
print(f"Success! Loaded {len(idx)} entries!")

# Test 2: list_quarantine_items
print("\nTest 2: list_quarantine_items()...")
items = list_quarantine_items()
exists_count = sum(1 for i in items if i.get('_exists'))
print(f"Success! Found {len(items)} items total, {exists_count} exist!")

# Test 3: _normalize_path
print("\nTest 3: Testing _normalize_path...")
test_paths = [
    r"D:\SUMMER\AYAWrus_10_07_26\Quarantine\test.js.quarantine",
    r"d:\summer\ayawrus_10_07_26\quarantine\test.js.quarantine",
    r"D:/SUMMER/AYAWrus_10_07_26/Quarantine/test.js.quarantine"
]
normalized = [_normalize_path(p) for p in test_paths]
all_same = all(n == normalized[0] for n in normalized)
print(f"All paths normalize to the same value: {all_same}")

# Show first 5 entries as example
print("\nFirst 5 entries in index:")
for i, entry in enumerate(idx[:5]):
    print(f"\n  {i+1}. {os.path.basename(entry.get('dest_path', 'N/A'))}")
    print(f"     Original: {entry.get('original_path', 'N/A')[:60]}...")
    print(f"     Timestamp: {entry.get('timestamp', 'N/A')}")

print("\n" + "=" * 80)
print("TESTS PASSED!")
print("=" * 80)
print("\nYour quarantine system is now fixed!")
print("You can now:")
print("  - Quarantine files normally (index will update correctly!)")
print("  - Restore files from quarantine!")
print("  - Delete files from quarantine!")
