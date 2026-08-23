package com.ayawrus.mobile;

import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class DashboardFragment extends Fragment {

    private TextView tvStatusBanner;
    private TextView tvLastScanFile;
    private TextView tvLastScanDetails;
    private TextView tvCleanCount;
    private TextView tvThreatCount;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        try {
            Log.i("AYAWrusDash", "onCreateView: inflating fragment_dashboard");
            View view = inflater.inflate(R.layout.fragment_dashboard, container, false);

            tvStatusBanner = view.findViewById(R.id.tvStatusBanner);
            tvLastScanFile = view.findViewById(R.id.tvLastScanFile);
            tvLastScanDetails = view.findViewById(R.id.tvLastScanDetails);
            tvCleanCount = view.findViewById(R.id.tvCleanCount);
            tvThreatCount = view.findViewById(R.id.tvThreatCount);

            if (tvStatusBanner == null || tvLastScanFile == null || tvLastScanDetails == null
                || tvCleanCount == null || tvThreatCount == null) {
                Log.e("AYAWrusDash", "One or more dashboard TextViews missing from layout!");
                return view;
            }

            refresh();
            Log.i("AYAWrusDash", "onCreateView finished");
            return view;
        } catch (Throwable t) {
            Log.e("AYAWrusDash", "Dashboard crashed during onCreateView", t);
            try {
                View fallback = inflater.inflate(R.layout.fragment_dashboard, container, false);
                TextView banner = fallback.findViewById(R.id.tvStatusBanner);
                if (banner != null) {
                    banner.setText("Dashboard Recovered");
                    banner.setBackgroundColor(0xFFFF9800);
                }
                return fallback;
            } catch (Throwable t2) {
                Log.e("AYAWrusDash", "Even fallback failed", t2);
                return new View(requireContext());
            }
        }
    }

    public void refresh() {
        if (tvStatusBanner == null) {
            Log.w("AYAWrusDash", "refresh() called before view was created — ignoring");
            return;
        }
        tvStatusBanner.setText("Refreshing…");
        tvStatusBanner.setBackgroundColor(0xFF2196F3);

        ApiClient.getService().getHistory(15).enqueue(new Callback<List<ScanResult>>() {
            @Override
            public void onResponse(Call<List<ScanResult>> call, Response<List<ScanResult>> response) {
                if (response.isSuccessful() && response.body() != null && !response.body().isEmpty()) {
                    applyData(response.body());
                    Log.i("AYAWrusDash", "refresh: API loaded " + response.body().size() + " results");
                } else {
                    Log.w("AYAWrusDash", "refresh: API returned empty/null — falling back to MockData");
                    applyData(MockData.getMockScanResults());
                }
            }

            @Override
            public void onFailure(Call<List<ScanResult>> call, Throwable t) {
                Log.w("AYAWrusDash", "refresh: API call failed, using MockData fallback: " + t.getMessage());
                applyData(MockData.getMockScanResults());
            }
        });
    }

    private void applyData(List<ScanResult> results) {
        if (results == null || results.isEmpty()) {
            tvStatusBanner.setText("System Online");
            tvStatusBanner.setBackgroundColor(0xFF4CAF50);
            tvLastScanFile.setText("No recent scans");
            tvLastScanDetails.setText("Waiting for scanner data");
            tvCleanCount.setText("0");
            tvThreatCount.setText("0");
            return;
        }

        int cleanCount = 0;
        int threatCount = 0;
        for (ScanResult result : results) {
            if (result == null) continue;
            String verdict = result.getVerdict() == null ? "" : result.getVerdict();
            if (verdict.equalsIgnoreCase("Clean")) {
                cleanCount++;
            } else {
                threatCount++;
            }
        }

        ScanResult lastScan = results.get(0);
        if (lastScan != null) {
            tvLastScanFile.setText(lastScan.getFileName() == null ? "—" : lastScan.getFileName());
            String details = (lastScan.getVerdict() == null ? "" : lastScan.getVerdict())
                + " • "
                + (lastScan.getDateScanned() == null ? "" : lastScan.getDateScanned());
            tvLastScanDetails.setText(details);
        }
        tvCleanCount.setText(String.valueOf(cleanCount));
        tvThreatCount.setText(String.valueOf(threatCount));

        if (threatCount > 0) {
            tvStatusBanner.setText("Threats Detected");
            tvStatusBanner.setBackgroundColor(0xFFF44336);
        } else {
            tvStatusBanner.setText("All Clear");
            tvStatusBanner.setBackgroundColor(0xFF4CAF50);
        }

        Log.i("AYAWrusDash", "applyData: clean=" + cleanCount + " threats=" + threatCount);
    }
}
