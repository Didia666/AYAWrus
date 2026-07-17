import os
import numpy as np
from datetime import datetime
from thrember.features import PEFeatureExtractor
from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from concurrent.futures import ProcessPoolExecutor, as_completed

from system.history.logs import view_logs
from system.history.reports import generate_incident_report
from system.quarantines.quarantine import process_quarantine
from system.scanner.scanner import regular_scan, quick_scan, custom_scan

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
