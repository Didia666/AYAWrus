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
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

import android.widget.Toast;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HistoryFragment extends Fragment {

    private ScanAdapter adapter;
    private List<ScanResult> allResults = new ArrayList<>();
    private TextView tvEmptyState;
    private RecyclerView rvScanHistory;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_history, container, false);

        rvScanHistory = view.findViewById(R.id.rvScanHistory);
        rvScanHistory.setLayoutManager(new LinearLayoutManager(getContext()));

        tvEmptyState = view.findViewById(R.id.tvEmptyState);

        adapter = new ScanAdapter(allResults);
        rvScanHistory.setAdapter(adapter);

        refresh();

        return view;
    }

    @Override
    public void onResume() {
        super.onResume();
        Log.i("AYAWrusHist", "onResume: refreshing history");
        refresh();
    }

    public void refresh() {
        Log.i("AYAWrusHist", "refresh() called — fetching history from API");
        if (tvEmptyState != null) {
            tvEmptyState.setVisibility(View.GONE);
        }
        fetchHistory();
    }

    private void fetchHistory() {
        ApiClient.getService().getHistory(15).enqueue(new Callback<List<ScanResult>>() {
            @Override
            public void onResponse(Call<List<ScanResult>> call, Response<List<ScanResult>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    updateList(response.body());
                    if (response.body().isEmpty()) {
                        Log.i("AYAWrusHist", "fetchHistory: API returned 0 records (server has no history yet)");
                    } else {
                        Log.i("AYAWrusHist", "fetchHistory: loaded " + response.body().size() + " records from API");
                    }
                } else {
                    Log.w("AYAWrusHist", "fetchHistory: API error (HTTP " + response.code() + "), showing demo mock data");
                    List<ScanResult> mock = filterLast15Days(MockData.getMockScanResults());
                    updateList(mock);
                    if (getContext() != null) {
                        Toast.makeText(getContext(), "API error — showing demo history. Check desktop server.", Toast.LENGTH_LONG).show();
                    }
                }
            }

            @Override
            public void onFailure(Call<List<ScanResult>> call, Throwable t) {
                Log.w("AYAWrusHist", "fetchHistory: API call failed: " + t.getMessage());
                List<ScanResult> mock = filterLast15Days(MockData.getMockScanResults());
                updateList(mock);
                if (getContext() != null) {
                    Toast.makeText(getContext(), "Connection error: " + t.getMessage() + " — showing demo data.", Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private void updateList(List<ScanResult> newResults) {
        allResults.clear();
        if (newResults != null) {
            allResults.addAll(newResults);
        }
        if (adapter != null) {
            adapter.notifyDataSetChanged();
        }
        updateEmptyStateVisibility();
    }

    private void updateEmptyStateVisibility() {
        if (tvEmptyState == null || rvScanHistory == null) return;
        if (allResults.isEmpty()) {
            tvEmptyState.setVisibility(View.VISIBLE);
            rvScanHistory.setVisibility(View.GONE);
        } else {
            tvEmptyState.setVisibility(View.GONE);
            rvScanHistory.setVisibility(View.VISIBLE);
        }
    }

    private List<ScanResult> filterLast15Days(List<ScanResult> results) {
        List<ScanResult> filtered = new ArrayList<>();
        long fifteenDaysAgo = System.currentTimeMillis() - (15L * 24 * 60 * 60 * 1000);

        for (ScanResult result : results) {
            if (result != null && result.getTimestamp() >= fifteenDaysAgo) {
                filtered.add(result);
            }
        }
        return filtered;
    }
}
