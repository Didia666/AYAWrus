#!/usr/bin/env python3
import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUARANTINE_DIR = os.path.join(BASE_DIR, "Quarantine")
QUARANTINE_INDEX_FILE = os.path.join(QUARANTINE_DIR, "quarantine_index.json")

print("=" * 80)
print("DIAGNOSING QUARANTINE INDEX ISSUE")
print("=" * 80)
print(f"Current directory: {BASE_DIR}")
print(f"QUARANTINE_DIR: {QUARANTINE_DIR}")
print(f"QUARANTINE_INDEX_FILE: {QUARANTINE_INDEX_FILE}")
print()

# Test 1: Load quarantine index and check paths
print("Test 1: Loading quarantine_index.json...")
try:
    with open(QUARANTINE_INDEX_FILE, 'r') as f:
        idx = json.load(f)
    print(f"Loaded {len(idx)} entries")
    
    print("\nEntry paths:")
    for i, entry in enumerate(idx):
        dest_exists = os.path.exists(entry.get("dest_path", ""))
        print(f"  [{i+1}] {entry.get('original_path', 'N/A')[:60]}...")
        print(f"       -> Dest exists: {dest_exists}")
        print(f"       -> Dest path: {entry.get('dest_path', 'N/A')[:80]}...")
        
        # Check if the dest path is in CURRENT quarantine folder
        current_dest = os.path.join(QUARANTINE_DIR, os.path.basename(entry.get("dest_path", "")))
        current_dest_exists = os.path.exists(current_dest)
        print(f"       -> File exists in CURRENT Quarantine folder: {current_dest_exists}")

except Exception as e:
    print(f"Error loading index: {e}")

# Test 2: Verify the files in CURRENT quarantine folder
print("\n" + "=" * 80)
print("Test 2: Files currently in Quarantine folder:")
try:
    files = os.listdir(QUARANTINE_DIR)
    quarantine_files = [f for f in files if f.endswith('.quarantine')]
    print(f"Found {len(quarantine_files)} .quarantine files")
    
    # Compare with index entries
    indexed_files = set([os.path.basename(e.get('dest_path', '')) for e in idx])
    current_files = set(quarantine_files)
    
    missing_from_index = current_files - indexed_files
    extra_in_index = indexed_files - current_files
    
    print(f"\n  Files in both index and folder: {len(current_files & indexed_files)}")
    print(f"  Files in folder but NOT in index: {len(missing_from_index)}")
    for f in sorted(missing_from_index):
        print(f"     - {f}")
    print(f"  Files in index but NOT in folder: {len(extra_in_index)}")
    for f in sorted(extra_in_index):
        print(f"     - {f}")

except Exception as e:
    print(f"Error listing files: {e}")

print("\n" + "=" * 80)
print("Diagnosis complete!")
