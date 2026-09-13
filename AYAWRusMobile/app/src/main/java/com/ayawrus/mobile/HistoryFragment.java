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
import androidx.fragment.app.FragmentActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;

import android.widget.Toast;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class HistoryFragment extends Fragment implements BatchAdapter.OnBatchClickListener {

    private BatchAdapter adapter;
    private List<ScanBatch> allBatches = new ArrayList<>();
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

        adapter = new BatchAdapter(allBatches, this);
        rvScanHistory.setAdapter(adapter);

        refresh();

        return view;
    }

    @Override
    public void onResume() {
        super.onResume();
        Log.i("AYAWrusHist", "onResume: refreshing history (batch list)");
        refresh();
    }

    public void refresh() {
        Log.i("AYAWrusHist", "refresh() called — fetching batches from API");
        if (tvEmptyState != null) {
            tvEmptyState.setVisibility(View.GONE);
        }
        fetchBatches();
    }

    private void fetchBatches() {
        ApiClient.getService().getBatches(30, 100).enqueue(new Callback<List<ScanBatch>>() {
            @Override
            public void onResponse(Call<List<ScanBatch>> call, Response<List<ScanBatch>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    updateList(response.body());
                    if (response.body().isEmpty()) {
                        Log.i("AYAWrusHist", "fetchBatches: API returned 0 batches — desktop has no scan runs yet");
                        if (getContext() != null) {
                            Toast.makeText(getContext(),
                                    "No scan batches on desktop yet. Run a scan first.",
                                    Toast.LENGTH_LONG).show();
                        }
                    } else {
                        Log.i("AYAWrusHist", "fetchBatches: loaded " + response.body().size() + " batches from API");
                    }
                } else {
                    Log.w("AYAWrusHist", "fetchBatches: API error (HTTP " + response.code() + "), showing demo mock batches");
                    List<ScanBatch> mock = MockData.getMockBatches();
                    updateList(mock);
                    if (getContext() != null) {
                        Toast.makeText(getContext(),
                                "API error — showing demo batches. Check desktop server.",
                                Toast.LENGTH_LONG).show();
                    }
                }
            }

            @Override
            public void onFailure(Call<List<ScanBatch>> call, Throwable t) {
                Log.w("AYAWrusHist", "fetchBatches: API call failed: " + t.getMessage());
                List<ScanBatch> mock = MockData.getMockBatches();
                updateList(mock);
                if (getContext() != null) {
                    Toast.makeText(getContext(),
                            "Connection error: " + t.getMessage() + " — showing demo batches.",
                            Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private void updateList(List<ScanBatch> newBatches) {
        allBatches.clear();
        if (newBatches != null) {
            allBatches.addAll(newBatches);
        }
        if (adapter != null) {
            adapter.setData(allBatches);
        }
        updateEmptyStateVisibility();
    }

    private void updateEmptyStateVisibility() {
        if (tvEmptyState == null || rvScanHistory == null) return;
        if (allBatches.isEmpty()) {
            tvEmptyState.setVisibility(View.VISIBLE);
            rvScanHistory.setVisibility(View.GONE);
        } else {
            tvEmptyState.setVisibility(View.GONE);
            rvScanHistory.setVisibility(View.VISIBLE);
        }
    }

    @Override
    public void onBatchClicked(ScanBatch batch) {
        if (batch == null) return;
        FragmentActivity activity = getActivity();
        if (activity == null) return;
        BatchDetailBottomSheet sheet = BatchDetailBottomSheet.newInstance(batch);
        sheet.show(activity.getSupportFragmentManager(), "BatchDetail");
    }
}
