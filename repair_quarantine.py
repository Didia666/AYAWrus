#!/usr/bin/env python3
import os
import json
import stat
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUARANTINE_DIR = os.path.join(BASE_DIR, "Quarantine")
QUARANTINE_INDEX_FILE = os.path.join(QUARANTINE_DIR, "quarantine_index.json")

print("=" * 80)
print("QUARANTINE INDEX REPAIR TOOL")
print("=" * 80)
print(f"Current directory: {BASE_DIR}")
print(f"Quarantine directory: {QUARANTINE_DIR}")
print()

# Step 1: Load existing index if it exists
existing_entries = []
if os.path.exists(QUARANTINE_INDEX_FILE):
    try:
        with open(QUARANTINE_INDEX_FILE, 'r') as f:
            existing_entries = json.load(f)
        print(f"Loaded {len(existing_entries)} existing entries from index")
    except Exception as e:
        print(f"Warning: Couldn't load existing index: {e}")

# Step 2: Get all .quarantine files in the folder
print("\nScanning Quarantine folder...")
quarantine_files = []
for filename in os.listdir(QUARANTINE_DIR):
    if filename.endswith('.quarantine') and filename != 'quarantine_index.json':
        filepath = os.path.join(QUARANTINE_DIR, filename)
        if os.path.isfile(filepath):
            quarantine_files.append((filename, filepath))

print(f"Found {len(quarantine_files)} .quarantine files in folder")

# Step 3: Build a map of files already in index (by filename)
indexed_filenames = {}
for entry in existing_entries:
    dest_path = entry.get('dest_path', '')
    if dest_path:
        fname = os.path.basename(dest_path)
        indexed_filenames[fname] = entry

# Step 4: Create new index entries for files not in index
new_entries = []
for filename, filepath in quarantine_files:
    # Check if already in index
    if filename in indexed_filenames:
        # Update the dest_path to the correct current path
        entry = indexed_filenames[filename].copy()
        entry['dest_path'] = filepath
        entry['_exists'] = True
        new_entries.append(entry)
    else:
        # Create new entry
        # Try to extract original filename (remove .quarantine)
        original_name = filename[:-10] if filename.endswith('.quarantine') else filename
        
        # Get file info
        file_size = os.path.getsize(filepath)
        mtime = os.path.getmtime(filepath)
        timestamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        new_entry = {
            "dest_path": filepath,
            "original_path": os.path.join(os.path.dirname(BASE_DIR), original_name),  # Best guess
            "timestamp": timestamp,
            "size": file_size,
            "result": "SUSPICIOUS",
            "probability": None,
            "_exists": True
        }
        new_entries.append(new_entry)

print(f"\nRepaired index will have {len(new_entries)} entries")

# Step 5: Make sure all files are read-only
print("\nEnsuring all files are read-only...")
for filename, filepath in quarantine_files:
    try:
        os.chmod(filepath, stat.S_IREAD)
    except Exception as e:
        print(f"Warning: Couldn't set permissions on {filename}: {e}")

# Step 6: Backup old index and save new one
backup_file = QUARANTINE_INDEX_FILE + '.backup_' + datetime.now().strftime("%Y%m%d_%H%M%S")
if os.path.exists(QUARANTINE_INDEX_FILE):
    os.rename(QUARANTINE_INDEX_FILE, backup_file)
    print(f"Backed up old index to: {os.path.basename(backup_file)}")

with open(QUARANTINE_INDEX_FILE, 'w') as f:
    # Remove _exists field before saving
    cleaned_entries = []
    for entry in new_entries:
        cleaned_entry = entry.copy()
        if '_exists' in cleaned_entry:
            del cleaned_entry['_exists']
        cleaned_entries.append(cleaned_entry)
    
    json.dump(cleaned_entries, f, indent=4)

print(f"\n✅ Successfully saved repaired index to: {os.path.basename(QUARANTINE_INDEX_FILE)}")
print("\n" + "=" * 80)
print("REPAIR COMPLETE!")
print("=" * 80)
print(f"Total files in index now: {len(cleaned_entries)}")
print("\nYou can now:")
print("  1. Use the restore_file() function to restore files")
print("  2. Use delete_file() to delete files you don't need")
