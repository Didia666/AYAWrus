package com.ayawrus.mobile;

public class ScanBatch {

    private String id;
    private String scanType;
    private String target;
    private String startedAt;
    private long startedAtMs;
    private String completedAt;
    private long completedAtMs;
    private long elapsedMs;
    private int totalFiles;
    private int cleanCount;
    private int threatCount;
    private int suspiciousCount;
    private int maliciousCount;
    private int errorCount;
    private String status;

    public ScanBatch() {
    }

    public ScanBatch(String id, String scanType, String target, String startedAt, long startedAtMs,
                     String completedAt, long completedAtMs, long elapsedMs,
                     int totalFiles, int cleanCount, int threatCount,
                     int suspiciousCount, int maliciousCount, int errorCount, String status) {
        this.id = id;
        this.scanType = scanType;
        this.target = target;
        this.startedAt = startedAt;
        this.startedAtMs = startedAtMs;
        this.completedAt = completedAt;
        this.completedAtMs = completedAtMs;
        this.elapsedMs = elapsedMs;
        this.totalFiles = totalFiles;
        this.cleanCount = cleanCount;
        this.threatCount = threatCount;
        this.suspiciousCount = suspiciousCount;
        this.maliciousCount = maliciousCount;
        this.errorCount = errorCount;
        this.status = status;
    }

    public String getId() { return id == null ? "" : id; }
    public String getScanType() { return scanType == null ? "" : scanType; }
    public String getTarget() { return target == null ? "" : target; }
    public String getStartedAt() { return startedAt == null ? "" : startedAt; }
    public long getStartedAtMs() { return startedAtMs; }
    public String getCompletedAt() { return completedAt == null ? "" : completedAt; }
    public long getCompletedAtMs() { return completedAtMs; }
    public long getElapsedMs() { return elapsedMs; }
    public int getTotalFiles() { return totalFiles; }
    public int getCleanCount() { return cleanCount; }
    public int getThreatCount() { return threatCount; }
    public int getSuspiciousCount() { return suspiciousCount; }
    public int getMaliciousCount() { return maliciousCount; }
    public int getErrorCount() { return errorCount; }
    public String getStatus() { return status == null ? "COMPLETED" : status; }

    public String getScanTypeLabel() {
        String st = getScanType().toLowerCase();
        switch (st) {
            case "quick":
            case "fast":
                return "Quick Scan";
            case "full":
            case "regular":
            case "system":
                return "Full System Scan";
            case "custom":
                return "Custom Scan";
            case "single":
                return "Single File";
            default:
                if (st.isEmpty()) return "Scan";
                return Character.toUpperCase(st.charAt(0)) + st.substring(1) + " Scan";
        }
    }

    public String getElapsedLabel() {
        long ms = Math.max(0L, elapsedMs);
        double sec = ms / 1000.0;
        if (sec < 60) {
            return String.format("%.1fs", sec);
        }
        long mins = (long) sec / 60;
        long secs = (long) sec % 60;
        return String.format("%dm %02ds", mins, secs);
    }

    public String getTargetTruncated(int maxLen) {
        String t = getTarget();
        if (t.length() <= maxLen) return t;
        return t.substring(0, Math.max(0, maxLen - 3)) + "...";
    }

    public boolean hasThreats() {
        return threatCount > 0 || maliciousCount > 0 || suspiciousCount > 0;
    }
}
