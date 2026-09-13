package com.ayawrus.mobile;

import android.content.Context;
import android.graphics.Color;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class BatchAdapter extends RecyclerView.Adapter<BatchAdapter.BatchViewHolder> {

    public interface OnBatchClickListener {
        void onBatchClicked(ScanBatch batch);
    }

    private List<ScanBatch> batches;
    private final OnBatchClickListener clickListener;

    public BatchAdapter(List<ScanBatch> batches, OnBatchClickListener listener) {
        this.batches = batches != null ? batches : new ArrayList<>();
        this.clickListener = listener;
    }

    public void setData(List<ScanBatch> newData) {
        if (newData == null) newData = new ArrayList<>();
        this.batches = newData;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public BatchViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_batch_card, parent, false);
        return new BatchViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull BatchViewHolder h, int position) {
        ScanBatch b = batches.get(position);
        if (b == null) return;

        h.tvBatchTitle.setText(b.getScanTypeLabel());
        String sub1 = String.format(Locale.US, "%d files", b.getTotalFiles());
        if (b.getCleanCount() > 0) sub1 += String.format(Locale.US, " · Clean %d", b.getCleanCount());
        if (b.getMaliciousCount() > 0) sub1 += String.format(Locale.US, " · Malicious %d", b.getMaliciousCount());
        if (b.getSuspiciousCount() > 0) sub1 += String.format(Locale.US, " · Suspicious %d", b.getSuspiciousCount());
        if (b.getErrorCount() > 0) sub1 += String.format(Locale.US, " · Errors %d", b.getErrorCount());
        h.tvBatchSub1.setText(sub1);

        String target = b.getTargetTruncated(64);
        String id = b.getId();
        String sub2;
        if (!target.isEmpty()) {
            sub2 = target;
            if (!id.isEmpty()) sub2 += String.format(Locale.US, " · %s", id);
        } else if (!id.isEmpty()) {
            sub2 = "Batch " + id;
        } else {
            sub2 = "";
        }
        String elapsed = b.getElapsedLabel();
        if (!sub2.isEmpty()) {
            sub2 += String.format(Locale.US, " · %s", elapsed);
        } else {
            sub2 = "Duration " + elapsed;
        }
        h.tvBatchSub2.setText(sub2);

        String status = b.getStatus().toUpperCase();
        if (status.isEmpty()) status = b.hasThreats() ? "COMPLETED" : "COMPLETED";
        h.tvBatchStatus.setText(status);

        int statusColor;
        if ("RUNNING".equals(status)) {
            statusColor = 0xFF2196F3;
        } else if ("FAILED".equals(status) || "CANCELLED".equals(status)) {
            statusColor = 0xFFF44336;
        } else if (b.hasThreats()) {
            statusColor = 0xFFF44336;
        } else {
            statusColor = 0xFF4CAF50;
        }
        h.tvBatchStatus.setTextColor(Color.WHITE);
        h.tvBatchStatus.setBackgroundColor(statusColor);

        if (b.getThreatCount() > 0) {
            h.tvThreatPill.setText(String.format(Locale.US, "⚠ %d threat%s",
                    b.getThreatCount(), b.getThreatCount() == 1 ? "" : "s"));
            h.tvThreatPill.setTextColor(Color.WHITE);
            h.tvThreatPill.setBackgroundColor(0xFFF44336);
            h.tvThreatPill.setVisibility(View.VISIBLE);
        } else {
            h.tvThreatPill.setText("✓ All clear");
            h.tvThreatPill.setTextColor(Color.WHITE);
            h.tvThreatPill.setBackgroundColor(0xFF4CAF50);
            h.tvThreatPill.setVisibility(View.VISIBLE);
        }

        String ts = !b.getStartedAt().isEmpty() ? b.getStartedAt()
                : (!b.getCompletedAt().isEmpty() ? b.getCompletedAt() : "");
        h.tvBatchDate.setText(ts);

        String st = b.getScanType().toLowerCase();
        int accent;
        switch (st) {
            case "quick": case "fast":
                accent = 0xFF2196F3; break;
            case "full": case "regular": case "system":
                accent = 0xFF6200EA; break;
            case "custom":
                accent = 0xFFFF9800; break;
            default:
                accent = 0xFF2196F3;
        }
        h.tvAccent.setBackgroundColor(accent);

        if (clickListener != null) {
            h.itemView.setOnClickListener(v -> clickListener.onBatchClicked(b));
        }
    }

    @Override
    public int getItemCount() {
        return batches.size();
    }

    static class BatchViewHolder extends RecyclerView.ViewHolder {
        TextView tvAccent;
        TextView tvBatchTitle;
        TextView tvBatchSub1;
        TextView tvBatchSub2;
        TextView tvBatchStatus;
        TextView tvThreatPill;
        TextView tvBatchDate;

        public BatchViewHolder(@NonNull View itemView) {
            super(itemView);
            tvAccent = itemView.findViewById(R.id.tvBatchAccent);
            tvBatchTitle = itemView.findViewById(R.id.tvBatchTitle);
            tvBatchSub1 = itemView.findViewById(R.id.tvBatchSub1);
            tvBatchSub2 = itemView.findViewById(R.id.tvBatchSub2);
            tvBatchStatus = itemView.findViewById(R.id.tvBatchStatus);
            tvThreatPill = itemView.findViewById(R.id.tvThreatPill);
            tvBatchDate = itemView.findViewById(R.id.tvBatchDate);
            if (tvAccent == null) {
                View stub = new View(itemView.getContext());
                stub.setLayoutParams(new ViewGroup.LayoutParams(0, 0));
            }
        }
    }
}
