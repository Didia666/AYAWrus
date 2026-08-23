package com.ayawrus.mobile;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.android.material.bottomsheet.BottomSheetDialogFragment;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ScanDetailBottomSheet extends BottomSheetDialogFragment {

    private static final String ARG_ID = "id";
    private static final String ARG_FILE_NAME = "fileName";
    private static final String ARG_VERDICT = "verdict";
    private static final String ARG_THREAT_LEVEL = "threatLevel";
    private static final String ARG_DATE_SCANNED = "dateScanned";
    private static final String ARG_STATUS = "status";

    // Call this to create the bottom sheet with a ScanResult's data
    public static ScanDetailBottomSheet newInstance(ScanResult result) {
        ScanDetailBottomSheet sheet = new ScanDetailBottomSheet();
        Bundle args = new Bundle();
        args.putString(ARG_ID, result.getId());
        args.putString(ARG_FILE_NAME, result.getFileName());
        args.putString(ARG_VERDICT, result.getVerdict());
        args.putInt(ARG_THREAT_LEVEL, result.getThreatLevel());
        args.putString(ARG_DATE_SCANNED, result.getDateScanned());
        args.putString(ARG_STATUS, result.getStatus());
        sheet.setArguments(args);
        return sheet;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.item_detail_bottom_sheet, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        Bundle args = getArguments();
        if (args == null) return;

        TextView tvFileName = view.findViewById(R.id.tvDetailFileName);
        TextView tvVerdict = view.findViewById(R.id.tvDetailVerdict);
        TextView tvThreatLevel = view.findViewById(R.id.tvDetailThreatLevel);
        TextView tvDate = view.findViewById(R.id.tvDetailDate);

        String fileName = args.getString(ARG_FILE_NAME);
        String verdict = args.getString(ARG_VERDICT);
        int threatLevel = args.getInt(ARG_THREAT_LEVEL);
        String dateScanned = args.getString(ARG_DATE_SCANNED);

        tvFileName.setText(fileName);
        tvVerdict.setText(verdict);
        tvThreatLevel.setText(String.valueOf(threatLevel));
        tvDate.setText(dateScanned);

        Button btnQuarantine = view.findViewById(R.id.btnQuarantine);
        String id = args.getString(ARG_ID);
        String status = args.getString(ARG_STATUS);

        // Show button only if malicious/suspicious and not already quarantined
        if (("Malicious".equals(verdict) || "Suspicious".equals(verdict)) && !"QUARANTINED".equals(status)) {
            btnQuarantine.setVisibility(View.VISIBLE);
        } else {
            btnQuarantine.setVisibility(View.GONE);
        }

        btnQuarantine.setOnClickListener(v -> {
            quarantineFile(id, btnQuarantine);
        });

        // Color the verdict badge to match the card
        switch (verdict) {
            case "Clean":
                tvVerdict.setBackgroundColor(0xFF4CAF50);
                break;
            case "Suspicious":
                tvVerdict.setBackgroundColor(0xFFFFC107);
                break;
            case "Malicious":
                tvVerdict.setBackgroundColor(0xFFF44336);
                break;
        }
    }

    private void quarantineFile(String id, Button button) {
        button.setEnabled(false);
        button.setText("Processing...");

        ApiClient.getService().quarantineFile(id).enqueue(new Callback<Void>() {
            @Override
            public void onResponse(Call<Void> call, Response<Void> response) {
                if (response.isSuccessful()) {
                    Toast.makeText(getContext(), "File quarantined successfully", Toast.LENGTH_SHORT).show();
                    button.setVisibility(View.GONE);
                    // In a real app, you'd update the local list/database too
                } else {
                    Toast.makeText(getContext(), "Failed to quarantine file", Toast.LENGTH_SHORT).show();
                    button.setEnabled(true);
                    button.setText("Quarantine");
                }
            }

            @Override
            public void onFailure(Call<Void> call, Throwable t) {
                Toast.makeText(getContext(), "Error: " + t.getMessage(), Toast.LENGTH_SHORT).show();
                button.setEnabled(true);
                button.setText("Quarantine");
            }
        });
    }
}
