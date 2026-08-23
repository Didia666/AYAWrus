package com.ayawrus.mobile;

public class ScanResult {

    private String id;
    private String fileName;
    private String verdict;      // "Clean", "Suspicious", "Malicious"
    private int threatLevel;     // 0-100
    private String dateScanned;
    private long timestamp;      // For easy filtering
    private String status;       // "ACTIVE", "QUARANTINED"

    public ScanResult(String id, String fileName, String verdict, int threatLevel, String dateScanned, long timestamp, String status) {
        this.id = id;
        this.fileName = fileName;
        this.verdict = verdict;
        this.threatLevel = threatLevel;
        this.dateScanned = dateScanned;
        this.timestamp = timestamp;
        this.status = status;
    }

    public String getId() {
        return id;
    }

    public String getFileName() {
        return fileName;
    }

    public String getVerdict() {
        return verdict;
    }

    public int getThreatLevel() {
        return threatLevel;
    }

    public String getDateScanned() {
        return dateScanned;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}