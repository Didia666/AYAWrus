package com.ayawrus.mobile;

import java.util.ArrayList;
import java.util.List;

public class MockData {

    public static List<ScanResult> getMockScanResults() {
        List<ScanResult> results = new ArrayList<>();
        long now = System.currentTimeMillis();
        long dayMillis = 24 * 60 * 60 * 1000L;

        results.add(new ScanResult("1", "resume.pdf", "Clean", 0, "2026-08-10", now - (4 * dayMillis), "ACTIVE"));
        results.add(new ScanResult("2", "installer.exe", "Malicious", 92, "2026-08-11", now - (3 * dayMillis), "ACTIVE"));
        results.add(new ScanResult("3", "photo.jpg", "Clean", 0, "2026-08-12", now - (2 * dayMillis), "ACTIVE"));
        results.add(new ScanResult("4", "crack_patch.zip", "Malicious", 78, "2026-08-12", now - (2 * dayMillis), "ACTIVE"));
        results.add(new ScanResult("5", "notes.docx", "Clean", 0, "2026-08-13", now - (1 * dayMillis), "ACTIVE"));
        results.add(new ScanResult("6", "suspicious_macro.xlsm", "Suspicious", 45, "2026-08-13", now - (1 * dayMillis), "ACTIVE"));

        return results;
    }
}