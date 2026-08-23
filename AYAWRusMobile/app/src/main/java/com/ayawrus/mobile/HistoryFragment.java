package com.ayawrus.mobile;

import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

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

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_history, container, false);

        RecyclerView rvScanHistory = view.findViewById(R.id.rvScanHistory);
        rvScanHistory.setLayoutManager(new LinearLayoutManager(getContext()));

        adapter = new ScanAdapter(allResults);
        rvScanHistory.setAdapter(adapter);

        refresh();

        return view;
    }

    public void refresh() {
        Log.i("AYAWrusHist", "refresh() called — fetching history from API");
        fetchHistory();
    }

    private void fetchHistory() {
        ApiClient.getService().getHistory(15).enqueue(new Callback<List<ScanResult>>() {
            @Override
            public void onResponse(Call<List<ScanResult>> call, Response<List<ScanResult>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    updateList(response.body());
                    Log.i("AYAWrusHist", "fetchHistory: loaded " + response.body().size() + " records from API");
                } else {
                    updateList(filterLast15Days(MockData.getMockScanResults()));
                    if (getContext() != null) {
                        Toast.makeText(getContext(), "Using mock data (API unavailable)", Toast.LENGTH_SHORT).show();
                    }
                }
            }

            @Override
            public void onFailure(Call<List<ScanResult>> call, Throwable t) {
                updateList(filterLast15Days(MockData.getMockScanResults()));
                if (getContext() != null) {
                    Toast.makeText(getContext(), "Error: " + t.getMessage() + ". Using mock data.", Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    private void updateList(List<ScanResult> newResults) {
        allResults.clear();
        allResults.addAll(newResults);
        if (adapter != null) {
            adapter.notifyDataSetChanged();
        }
    }

    private List<ScanResult> filterLast15Days(List<ScanResult> results) {
        List<ScanResult> filtered = new ArrayList<>();
        long fifteenDaysAgo = System.currentTimeMillis() - (15L * 24 * 60 * 60 * 1000);

        for (ScanResult result : results) {
            if (result.getTimestamp() >= fifteenDaysAgo) {
                filtered.add(result);
            }
        }
        return filtered;
    }
}
