package com.ayawrus.mobile;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.fragment.app.FragmentActivity;
import androidx.recyclerview.widget.RecyclerView;

import java.util.List;

public class ScanAdapter extends RecyclerView.Adapter<ScanAdapter.ScanViewHolder> {

    private List<ScanResult> scanResults;

    public ScanAdapter(List<ScanResult> scanResults) {
        this.scanResults = scanResults;
    }

    @NonNull
    @Override
    public ScanViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_scan_card, parent, false);
        return new ScanViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ScanViewHolder holder, int position) {
        ScanResult result = scanResults.get(position);

        holder.tvFileName.setText(result.getFileName());
        holder.tvVerdict.setText(result.getVerdict());
        holder.tvDate.setText(result.getDateScanned());

        if ("QUARANTINED".equals(result.getStatus())) {
            holder.tvQuarantinedBadge.setVisibility(View.VISIBLE);
        } else {
            holder.tvQuarantinedBadge.setVisibility(View.GONE);
        }

        // Color the verdict badge based on result
        switch (result.getVerdict()) {
            case "Clean":
                holder.tvVerdict.setBackgroundColor(0xFF4CAF50); // green
                break;
            case "Suspicious":
                holder.tvVerdict.setBackgroundColor(0xFFFFC107); // yellow
                break;
            case "Malicious":
                holder.tvVerdict.setBackgroundColor(0xFFF44336); // red
                break;
        }

        // Tap card to show full details in a bottom sheet
        holder.itemView.setOnClickListener(v -> {
            FragmentActivity activity = (FragmentActivity) v.getContext();
            ScanDetailBottomSheet sheet = ScanDetailBottomSheet.newInstance(result);
            sheet.show(activity.getSupportFragmentManager(), "ScanDetail");
        });
    }

    @Override
    public int getItemCount() {
        return scanResults.size();
    }

    static class ScanViewHolder extends RecyclerView.ViewHolder {
        TextView tvFileName;
        TextView tvVerdict;
        TextView tvDate;
        TextView tvQuarantinedBadge;

        public ScanViewHolder(@NonNull View view) {
            super(view);
            tvFileName = view.findViewById(R.id.tvFileName);
            tvVerdict = view.findViewById(R.id.tvVerdict);
            tvDate = view.findViewById(R.id.tvDate);
            tvQuarantinedBadge = view.findViewById(R.id.tvQuarantinedBadge);
        }
    }
}
