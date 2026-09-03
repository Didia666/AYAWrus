package com.ayawrus.mobile;

import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class QuarantineFragment extends Fragment {

    private static final String TAG = "AYAWrusQ";

    private ScanAdapter adapter;
    private List<ScanResult> threats = new ArrayList<>();
    private RecyclerView rvThreats;
    private TextView tvEmptyState;
    private TextView tvSelectionCount;
    private Button btnQuarantineSelected;
    private volatile boolean quarantineInProgress = false;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_quarantine, container, false);

        rvThreats = view.findViewById(R.id.rvThreats);
        rvThreats.setLayoutManager(new LinearLayoutManager(getContext()));

        tvEmptyState = view.findViewById(R.id.tvEmptyState);
        tvSelectionCount = view.findViewById(R.id.tvSelectionCount);
        btnQuarantineSelected = view.findViewById(R.id.btnQuarantineSelected);

        adapter = new ScanAdapter(threats, true, (selected, total) -> {
            updateSelectionUi(selected, total);
        });
        rvThreats.setAdapter(adapter);

        btnQuarantineSelected.setOnClickListener(v -> quarantineSelected());
        updateSelectionUi(0, threats.size());
        refresh();
        return view;
    }

    @Override
    public void onResume() {
        super.onResume();
        Log.i(TAG, "onResume: refreshing quarantine list");
        refresh();
    }

    public void refresh() {
        if (tvEmptyState != null) {
            tvEmptyState.setVisibility(View.GONE);
        }
        fetchThreats();
    }

    private void fetchThreats() {
        ApiClient.getService().getHistory(15).enqueue(new Callback<List<ScanResult>>() {
            @Override
            public void onResponse(Call<List<ScanResult>> call, Response<List<ScanResult>> response) {
                List<ScanResult> filtered = new ArrayList<>();
                if (response.isSuccessful() && response.body() != null) {
                    for (ScanResult r : response.body()) {
                        if (r == null) continue;
                        String verdict = r.getVerdict() == null ? "" : r.getVerdict();
                        String status = r.getStatus() == null ? "ACTIVE" : r.getStatus();
                        boolean isThreat = verdict.equalsIgnoreCase("Malicious")
                                || verdict.equalsIgnoreCase("Suspicious");
                        boolean isActive = !"QUARANTINED".equalsIgnoreCase(status);
                        if (isThreat && isActive) {
                            filtered.add(r);
                        }
                    }
                    Log.i(TAG, "fetchThreats: API returned " + response.body().size()
                            + " total, " + filtered.size() + " active threats");
                } else {
                    Log.w(TAG, "fetchThreats: API HTTP " + response.code());
                    if (getContext() != null) {
                        Toast.makeText(getContext(), "API error (" + response.code() + ") — could not load threats", Toast.LENGTH_LONG).show();
                    }
                }
                applyThreatList(filtered);
            }

            @Override
            public void onFailure(Call<List<ScanResult>> call, Throwable t) {
                Log.w(TAG, "fetchThreats: network failure: " + t.getMessage());
                if (getContext() != null) {
                    Toast.makeText(getContext(),
                            "Cannot reach desktop server: " + t.getMessage(),
                            Toast.LENGTH_LONG).show();
                }
                applyThreatList(new ArrayList<>());
            }
        });
    }

    private void applyThreatList(List<ScanResult> filtered) {
        threats.clear();
        if (filtered != null) {
            threats.addAll(filtered);
        }
        adapter.setData(threats);
        updateEmptyState();
        updateSelectionUi(adapter.getSelectedCount(), threats.size());
    }

    private void updateSelectionUi(int selected, int total) {
        if (tvSelectionCount == null || btnQuarantineSelected == null) return;
        tvSelectionCount.setText(selected + " selected / " + total + " threats");
        boolean enabled = !quarantineInProgress && selected > 0;
        btnQuarantineSelected.setEnabled(enabled);
        btnQuarantineSelected.setAlpha(enabled ? 1.0f : 0.5f);
        if (quarantineInProgress) {
            btnQuarantineSelected.setText("Quarantining…");
        } else if (selected == 0) {
            btnQuarantineSelected.setText("Quarantine Selected");
        } else {
            btnQuarantineSelected.setText("Quarantine " + selected);
        }
    }

    private void updateEmptyState() {
        if (tvEmptyState == null || rvThreats == null) return;
        if (threats.isEmpty()) {
            tvEmptyState.setVisibility(View.VISIBLE);
            rvThreats.setVisibility(View.GONE);
        } else {
            tvEmptyState.setVisibility(View.GONE);
            rvThreats.setVisibility(View.VISIBLE);
        }
    }

    private void quarantineSelected() {
        final List<ScanResult> selected = adapter.getSelectedItems();
        if (selected == null || selected.isEmpty()) {
            if (getContext() != null) {
                Toast.makeText(getContext(), "Select at least one threat first", Toast.LENGTH_SHORT).show();
            }
            return;
        }
        if (quarantineInProgress) return;
        quarantineInProgress = true;
        updateSelectionUi(adapter.getSelectedCount(), threats.size());
        Log.i(TAG, "quarantineSelected: sending " + selected.size() + " remote quarantine requests");

        final AtomicInteger successCount = new AtomicInteger(0);
        final AtomicInteger failCount = new AtomicInteger(0);
        final int total = selected.size();

        for (final ScanResult r : selected) {
            final String id = r.getId();
            if (id == null) {
                failCount.incrementAndGet();
                continue;
            }
            ApiClient.getService().quarantineFile(id).enqueue(new Callback<Void>() {
                @Override
                public void onResponse(Call<Void> call, Response<Void> response) {
                    boolean ok = response.isSuccessful();
                    if (ok) {
                        successCount.incrementAndGet();
                        adapter.markItemQuarantined(id);
                        Log.i(TAG, "quarantine OK: id=" + id + " file=" + r.getFileName());
                    } else {
                        failCount.incrementAndGet();
                        Log.w(TAG, "quarantine FAIL HTTP " + response.code() + " for id=" + id);
                    }
                    checkFinish(total, successCount.get(), failCount.get());
                }

                @Override
                public void onFailure(Call<Void> call, Throwable t) {
                    failCount.incrementAndGet();
                    Log.w(TAG, "quarantine FAIL network for id=" + id + ": " + t.getMessage());
                    checkFinish(total, successCount.get(), failCount.get());
                }
            });
        }
    }

    private void checkFinish(int expected, int success, int fail) {
        int seen = success + fail;
        if (seen < expected) return;
        quarantineInProgress = false;
        int remainingThreats = 0;
        for (ScanResult r : threats) {
            if (r == null) continue;
            if (!"QUARANTINED".equalsIgnoreCase(r.getStatus())) {
                remainingThreats++;
            }
        }
        updateSelectionUi(0, remainingThreats);
        updateEmptyState();
        if (getContext() != null) {
            String msg = success + " file(s) quarantined on desktop";
            if (fail > 0) {
                msg += ". " + fail + " failed.";
            }
            Toast.makeText(getContext(), msg, Toast.LENGTH_LONG).show();
        }
    }
}
