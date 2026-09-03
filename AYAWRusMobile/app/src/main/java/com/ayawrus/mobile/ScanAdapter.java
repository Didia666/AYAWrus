package com.ayawrus.mobile;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.fragment.app.FragmentActivity;
import androidx.recyclerview.widget.RecyclerView;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class ScanAdapter extends RecyclerView.Adapter<ScanAdapter.ScanViewHolder> {

    private List<ScanResult> scanResults;
    private final boolean selectable;
    private final Set<String> selectedIds = new HashSet<>();
    private final OnSelectionChangedListener selectionListener;

    public interface OnSelectionChangedListener {
        void onSelectionChanged(int selectedCount, int totalCount);
    }

    public ScanAdapter(List<ScanResult> scanResults) {
        this(scanResults, false, null);
    }

    public ScanAdapter(List<ScanResult> scanResults, boolean selectable,
                       OnSelectionChangedListener selectionListener) {
        this.scanResults = scanResults != null ? scanResults : new ArrayList<>();
        this.selectable = selectable;
        this.selectionListener = selectionListener;
    }

    public void setData(List<ScanResult> newData) {
        if (newData == null) {
            newData = new ArrayList<>();
        }
        this.scanResults = newData;
        selectedIds.retainAll(toIdSet(newData));
        notifyDataSetChanged();
        fireSelectionChanged();
    }

    public List<ScanResult> getSelectedItems() {
        List<ScanResult> out = new ArrayList<>();
        for (ScanResult r : scanResults) {
            if (r != null && r.getId() != null && selectedIds.contains(r.getId())) {
                out.add(r);
            }
        }
        return out;
    }

    public int getSelectedCount() {
        return selectedIds.size();
    }

    public void clearSelection() {
        selectedIds.clear();
        notifyDataSetChanged();
        fireSelectionChanged();
    }

    public void markItemQuarantined(String id) {
        if (id == null) return;
        for (int i = 0; i < scanResults.size(); i++) {
            ScanResult r = scanResults.get(i);
            if (r != null && id.equals(r.getId())) {
                r.setStatus("QUARANTINED");
                notifyItemChanged(i);
                break;
            }
        }
        selectedIds.remove(id);
        fireSelectionChanged();
    }

    private Set<String> toIdSet(List<ScanResult> list) {
        Set<String> s = new HashSet<>();
        for (ScanResult r : list) {
            if (r != null && r.getId() != null) {
                s.add(r.getId());
            }
        }
        return s;
    }

    private void fireSelectionChanged() {
        if (selectionListener != null) {
            selectionListener.onSelectionChanged(selectedIds.size(), scanResults.size());
        }
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

        switch (result.getVerdict() == null ? "" : result.getVerdict()) {
            case "Clean":
                holder.tvVerdict.setBackgroundColor(0xFF4CAF50);
                break;
            case "Suspicious":
                holder.tvVerdict.setBackgroundColor(0xFFFFC107);
                break;
            case "Malicious":
                holder.tvVerdict.setBackgroundColor(0xFFF44336);
                break;
            default:
                holder.tvVerdict.setBackgroundColor(0xFF9E9E9E);
                break;
        }

        if (selectable) {
            holder.cbSelect.setVisibility(View.VISIBLE);
            boolean selectableForThisItem = !"QUARANTINED".equals(result.getStatus());
            holder.cbSelect.setEnabled(selectableForThisItem);
            holder.cbSelect.setAlpha(selectableForThisItem ? 1.0f : 0.4f);

            String id = result.getId();
            boolean isSelected = id != null && selectedIds.contains(id);

            holder.cbSelect.setOnCheckedChangeListener(null);
            holder.cbSelect.setChecked(isSelected);

            final CompoundButton.OnCheckedChangeListener listener = (buttonView, isChecked) -> {
                if (!selectableForThisItem) return;
                if (id == null) return;
                if (isChecked) {
                    selectedIds.add(id);
                } else {
                    selectedIds.remove(id);
                }
                fireSelectionChanged();
            };
            holder.cbSelect.setOnCheckedChangeListener(listener);

            holder.itemView.setOnClickListener(v -> {
                if (!selectableForThisItem) return;
                holder.cbSelect.toggle();
            });
        } else {
            holder.cbSelect.setVisibility(View.GONE);
            holder.cbSelect.setOnCheckedChangeListener(null);
            holder.itemView.setOnClickListener(v -> {
                FragmentActivity activity = (FragmentActivity) v.getContext();
                ScanDetailBottomSheet sheet = ScanDetailBottomSheet.newInstance(result);
                sheet.show(activity.getSupportFragmentManager(), "ScanDetail");
            });
        }
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
        CheckBox cbSelect;

        public ScanViewHolder(@NonNull View view) {
            super(view);
            tvFileName = view.findViewById(R.id.tvFileName);
            tvVerdict = view.findViewById(R.id.tvVerdict);
            tvDate = view.findViewById(R.id.tvDate);
            tvQuarantinedBadge = view.findViewById(R.id.tvQuarantinedBadge);
            cbSelect = view.findViewById(R.id.cbSelect);
        }
    }
}
