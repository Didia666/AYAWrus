package com.ayawrus.mobile;

import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.FragmentActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.bottomsheet.BottomSheetDialogFragment;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class BatchDetailBottomSheet extends BottomSheetDialogFragment {

    private static final String ARG_ID = "id";
    private static final String ARG_SCAN_TYPE = "scanType";
    private static final String ARG_STARTED_AT = "startedAt";
    private static final String ARG_TOTAL = "total";
    private static final String ARG_THREATS = "threats";
    private static final String ARG_STATUS = "status";
    private static final String ARG_ELAPSED = "elapsed";

    private TextView tvTitle;
    private TextView tvSubtitle;
    private TextView tvStats;
    private TextView tvEmpty;
    private RecyclerView rvFiles;
    private LinearLayout loadingWrap;
    private ScanAdapter adapter;
    private String batchId;

    public static BatchDetailBottomSheet newInstance(ScanBatch batch) {
        BatchDetailBottomSheet sheet = new BatchDetailBottomSheet();
        Bundle args = new Bundle();
        args.putString(ARG_ID, batch.getId());
        args.putString(ARG_SCAN_TYPE, batch.getScanTypeLabel());
        args.putString(ARG_STARTED_AT, batch.getStartedAt());
        args.putInt(ARG_TOTAL, batch.getTotalFiles());
        args.putInt(ARG_THREATS, batch.getThreatCount());
        args.putString(ARG_STATUS, batch.getStatus());
        args.putLong(ARG_ELAPSED, batch.getElapsedMs());
        sheet.setArguments(args);
        return sheet;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.item_batch_detail_bottom_sheet, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        tvTitle = view.findViewById(R.id.tvBatchDetailTitle);
        tvSubtitle = view.findViewById(R.id.tvBatchDetailSubtitle);
        tvStats = view.findViewById(R.id.tvBatchDetailStats);
        tvEmpty = view.findViewById(R.id.tvBatchDetailEmpty);
        rvFiles = view.findViewById(R.id.rvBatchFiles);
        loadingWrap = view.findViewById(R.id.batchDetailLoadingWrap);

        rvFiles.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new ScanAdapter(new ArrayList<>());
        rvFiles.setAdapter(adapter);

        Bundle args = getArguments();
        batchId = args == null ? "" : args.getString(ARG_ID, "");
        String scanTypeLabel = args == null ? "Scan" : args.getString(ARG_SCAN_TYPE, "Scan");
        String startedAt = args == null ? "" : args.getString(ARG_STARTED_AT, "");
        int total = args == null ? 0 : args.getInt(ARG_TOTAL, 0);
        int threats = args == null ? 0 : args.getInt(ARG_THREATS, 0);
        String status = args == null ? "" : args.getString(ARG_STATUS, "COMPLETED");
        long elapsedMs = args == null ? 0L : args.getLong(ARG_ELAPSED, 0L);

        String title = total > 0
                ? String.format(Locale.US, "%s — %d files", scanTypeLabel, total)
                : scanTypeLabel;
        tvTitle.setText(title);

        StringBuilder sb = new StringBuilder();
        if (!startedAt.isEmpty()) sb.append("Started ").append(startedAt);
        if (elapsedMs > 0) {
            double sec = elapsedMs / 1000.0;
            String el;
            if (sec < 60) el = String.format(Locale.US, "%.1fs", sec);
            else el = String.format(Locale.US, "%dm %02ds", (long)(sec/60), (long)(sec%60));
            if (sb.length() > 0) sb.append("   ·   ");
            sb.append("Duration ").append(el);
        }
        if (!status.isEmpty()) {
            if (sb.length() > 0) sb.append("   ·   ");
            sb.append(status);
        }
        tvSubtitle.setText(sb.toString());
        tvStats.setVisibility(View.GONE);

        Button btnClose = view.findViewById(R.id.btnBatchClose);
        if (btnClose != null) {
            btnClose.setOnClickListener(v -> dismiss());
        }

        fetchFiles(batchId);
    }

    private void fetchFiles(String id) {
        if (id == null || id.isEmpty()) {
            showEmpty("Missing batch ID.");
            return;
        }
        showLoading(true);
        ApiClient.getService().getBatchFiles(id).enqueue(new Callback<BatchFilesResponse>() {
            @Override
            public void onResponse(Call<BatchFilesResponse> call, Response<BatchFilesResponse> response) {
                showLoading(false);
                if (response.isSuccessful() && response.body() != null) {
                    BatchFilesResponse data = response.body();
                    ScanBatch b = data.batch;
                    if (b != null) {
                        String stats = String.format(Locale.US,
                                "Clean %d · Malicious %d · Suspicious %d",
                                b.getCleanCount(), b.getMaliciousCount(), b.getSuspiciousCount());
                        if (b.getErrorCount() > 0) {
                            stats += String.format(Locale.US, " · Errors %d", b.getErrorCount());
                        }
                        tvStats.setText(stats);
                        tvStats.setVisibility(View.VISIBLE);
                    }
                    List<ScanResult> files = data.files;
                    if (files == null) files = new ArrayList<>();
                    applyFiles(files);
                } else {
                    applyFilesMockFallback(id);
                }
            }

            @Override
            public void onFailure(Call<BatchFilesResponse> call, Throwable t) {
                showLoading(false);
                applyFilesMockFallback(id);
            }
        });
    }

    private void applyFilesMockFallback(String id) {
        List<ScanResult> mock = filterBatchMock(id);
        if (mock.isEmpty()) {
            if (getContext() != null) {
                Toast.makeText(getContext(), "Couldn't load batch detail — showing offline.",
                        Toast.LENGTH_LONG).show();
            }
        }
        applyFiles(mock);
    }

    private List<ScanResult> filterBatchMock(String batchId) {
        List<ScanResult> all = new ArrayList<>();
        try {
            all = MockData.getMockScanResults();
        } catch (Exception ignore) {
        }
        if (all == null || all.isEmpty()) return new ArrayList<>();
        return all;
    }

    private void applyFiles(List<ScanResult> files) {
        if (adapter != null) {
            adapter.setData(files);
        }
        if (files == null || files.isEmpty()) {
            tvEmpty.setVisibility(View.VISIBLE);
            rvFiles.setVisibility(View.GONE);
        } else {
            tvEmpty.setVisibility(View.GONE);
            rvFiles.setVisibility(View.VISIBLE);
        }
    }

    private void showLoading(boolean show) {
        if (loadingWrap != null) {
            loadingWrap.setVisibility(show ? View.VISIBLE : View.GONE);
        }
    }

    private void showEmpty(String msg) {
        showLoading(false);
        if (tvEmpty != null) {
            tvEmpty.setText(msg);
            tvEmpty.setVisibility(View.VISIBLE);
        }
        if (rvFiles != null) rvFiles.setVisibility(View.GONE);
    }
}
