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

    public static List<ScanBatch> getMockBatches() {
        List<ScanBatch> out = new ArrayList<>();
        long now = System.currentTimeMillis();
        long day = 24 * 60 * 60 * 1000L;

        ScanBatch b1 = new ScanBatch(
                "BDEMO00000000001", "quick", "C:\\Users\\Me\\Downloads",
                "2026-09-03 12:05:10", now - (12 * 60 * 1000L),
                "2026-09-03 12:05:42", now - (11 * 60 * 1000L + 28 * 1000L),
                32100L,
                142, 140, 2, 1, 1, 0, "COMPLETED"
        );
        ScanBatch b2 = new ScanBatch(
                "BDEMO00000000002", "full", "C:\\Windows, C:\\Program Files, C:\\Users",
                "2026-09-02 22:00:02", now - (1 * day + 2 * 60 * 60 * 1000L),
                "2026-09-02 22:14:38", now - (1 * day + 1 * 60 * 60 * 1000L + 45 * 60 * 1000L + 24 * 1000L),
                876_000L,
                15_420, 15_408, 12, 3, 9, 0, "COMPLETED"
        );
        ScanBatch b3 = new ScanBatch(
                "BDEMO00000000003", "custom", "D:\\Projects\\AYAWrus",
                "2026-09-02 10:41:50", now - (1 * day + 13 * 60 * 60 * 1000L),
                "2026-09-02 10:41:58", now - (1 * day + 13 * 60 * 60 * 1000L + 8 * 1000L),
                8_400L,
                318, 318, 0, 0, 0, 0, "COMPLETED"
        );
        ScanBatch b4 = new ScanBatch(
                "BDEMO00000000004", "quick", "C:\\Users\\Me\\Desktop",
                "2026-09-01 18:22:05", now - (2 * day + 5 * 60 * 60 * 1000L),
                "2026-09-01 18:22:16", now - (2 * day + 5 * 60 * 60 * 1000L + 11 * 1000L),
                11_200L,
                56, 56, 0, 0, 0, 0, "COMPLETED"
        );

        out.add(b1);
        out.add(b2);
        out.add(b3);
        out.add(b4);
        return out;
    }
}