import os
from concurrent.futures import ProcessPoolExecutor, as_completed

from system.config import REGULAR_SCAN_DIRS, QUICK_SCAN_DIRS
from system.history.logs import begin_log_buffer, flush_log_buffer
from system.xai.display import display_xai_explanation
from system.scanner.file_scan import scan_file
from system.scanner.folder_scan import scan_folder_parallel


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