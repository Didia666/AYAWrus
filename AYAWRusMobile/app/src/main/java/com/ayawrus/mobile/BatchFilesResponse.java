package com.ayawrus.mobile;

import java.util.List;

public class BatchFilesResponse {

    public String id;
    public ScanBatch batch;
    public List<ScanResult> files;
    public int total;

    public BatchFilesResponse() {
    }
}
