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
        try {
            ScanDetailBottomSheet sheet = new ScanDetailBottomSheet();
            Bundle args = new Bundle();
            if (result == null) {
                sheet.setArguments(args);
                return sheet;
            }
            args.putString(ARG_ID, result.getId());
            args.putString(ARG_FILE_NAME, result.getFileName());
            args.putString(ARG_VERDICT, result.getVerdict());
            args.putInt(ARG_THREAT_LEVEL, result.getThreatLevel());
            args.putString(ARG_DATE_SCANNED, result.getDateScanned());
            args.putString(ARG_STATUS, result.getStatus());
            sheet.setArguments(args);
            return sheet;
        } catch (Throwable t) {
            android.util.Log.e("AYAWrusScanDetail", "Could not build detail args", t);
            return new ScanDetailBottomSheet();
        }
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
        try {
            Bundle args = getArguments();
            if (args == null) {
                android.util.Log.w("AYAWrusScanDetail", "onViewCreated: no args bundle");
                return;
            }

            TextView tvFileName = view.findViewById(R.id.tvDetailFileName);
            TextView tvVerdict = view.findViewById(R.id.tvDetailVerdict);
            TextView tvThreatLevel = view.findViewById(R.id.tvDetailThreatLevel);
            TextView tvDate = view.findViewById(R.id.tvDetailDate);

            if (tvFileName == null || tvVerdict == null || tvThreatLevel == null || tvDate == null) {
                android.util.Log.w("AYAWrusScanDetail", "onViewCreated: one or more required views missing");
                return;
            }

            String fileName = args.getString(ARG_FILE_NAME, "");
            String verdict = args.getString(ARG_VERDICT);
            int threatLevel;
            try {
                threatLevel = args.getInt(ARG_THREAT_LEVEL, 0);
            } catch (Throwable _t) {
                threatLevel = 0;
            }
            String dateScanned = args.getString(ARG_DATE_SCANNED, "");
            String normalizedVerdict = verdict == null ? "" : verdict.trim();

            tvFileName.setText(fileName == null ? "" : fileName);
            tvVerdict.setText(normalizedVerdict.isEmpty() ? "Unknown" : normalizedVerdict);
            try {
                tvThreatLevel.setText(String.valueOf(threatLevel));
            } catch (Throwable _t) {
                tvThreatLevel.setText("0");
            }
            tvDate.setText(dateScanned == null ? "" : dateScanned);

            Button btnQuarantine = view.findViewById(R.id.btnQuarantine);
            String id = args.getString(ARG_ID, "");
            String status = args.getString(ARG_STATUS, "");

            if (("Malicious".equals(normalizedVerdict) || "Suspicious".equals(normalizedVerdict))
                    && !"QUARANTINED".equalsIgnoreCase(status)) {
                if (btnQuarantine != null) {
                    btnQuarantine.setVisibility(View.VISIBLE);
                }
            } else if (btnQuarantine != null) {
                btnQuarantine.setVisibility(View.GONE);
            }

            if (btnQuarantine != null) {
                btnQuarantine.setOnClickListener(v -> {
                    try {
                        quarantineFile(id, btnQuarantine);
                    } catch (Throwable t) {
                        android.util.Log.e("AYAWrusScanDetail", "Quarantine click crashed", t);
                        if (getContext() != null) {
                            Toast.makeText(getContext(), "Unable to quarantine right now.", Toast.LENGTH_SHORT).show();
                        }
                    }
                });
            }

            try {
                UiStyle.applyTone(tvVerdict, UiStyle.toneForVerdict(normalizedVerdict));
            } catch (Throwable t) {
                android.util.Log.w("AYAWrusScanDetail", "UiStyle.applyTone failed", t);
            }
        } catch (Throwable t) {
            android.util.Log.e("AYAWrusScanDetail", "onViewCreated top-level crash", t);
            if (getContext() != null) {
                Toast.makeText(getContext(), "Unable to show file details.", Toast.LENGTH_SHORT).show();
            }
            try { dismiss(); } catch (Throwable ignore) {}
        }
    }

    private void quarantineFile(String id, Button button) {
        if (button == null || id == null || id.isEmpty()) return;
        try {
            button.setEnabled(false);
            button.setText("Processing...");
        } catch (Throwable _t) { /* ignore */ }

        try {
            ApiClient.getService().quarantineFile(id).enqueue(new Callback<Void>() {
                @Override
                public void onResponse(Call<Void> call, Response<Void> response) {
                    try {
                        if (response.isSuccessful()) {
                            if (getContext() != null) {
                                Toast.makeText(getContext(), "File quarantined successfully", Toast.LENGTH_SHORT).show();
                            }
                            try { button.setVisibility(View.GONE); } catch (Throwable _t) {}
                        } else {
                            if (getContext() != null) {
                                Toast.makeText(getContext(), "Failed to quarantine file", Toast.LENGTH_SHORT).show();
                            }
                            try {
                                button.setEnabled(true);
                                button.setText("Quarantine");
                            } catch (Throwable _t) {}
                        }
                    } catch (Throwable t) {
                        android.util.Log.w("AYAWrusScanDetail", "quarantine onResponse crashed", t);
                    }
                }

                @Override
                public void onFailure(Call<Void> call, Throwable t) {
                    try {
                        if (getContext() != null) {
                            String msg = t != null && t.getMessage() != null ? t.getMessage() : "Network error";
                            Toast.makeText(getContext(), "Error: " + msg, Toast.LENGTH_SHORT).show();
                        }
                        button.setEnabled(true);
                        button.setText("Quarantine");
                    } catch (Throwable _t) {
                        android.util.Log.w("AYAWrusScanDetail", "quarantine onFailure crashed", _t);
                    }
                }
            });
        } catch (Throwable t) {
            android.util.Log.e("AYAWrusScanDetail", "quarantineFile enqueue crashed", t);
            try {
                button.setEnabled(true);
                button.setText("Quarantine");
            } catch (Throwable _t) {}
            if (getContext() != null) {
                Toast.makeText(getContext(), "Unable to send quarantine request.", Toast.LENGTH_SHORT).show();
            }
        }
    }
}
