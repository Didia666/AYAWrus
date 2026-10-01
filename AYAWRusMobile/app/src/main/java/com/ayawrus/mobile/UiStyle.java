package com.ayawrus.mobile;

import android.widget.TextView;

import androidx.annotation.ColorRes;
import androidx.annotation.DrawableRes;
import androidx.core.content.ContextCompat;

public final class UiStyle {

    public static final int TONE_CLEAN = 0;
    public static final int TONE_THREAT = 1;
    public static final int TONE_WARNING = 2;
    public static final int TONE_INFO = 3;
    public static final int TONE_NEUTRAL = 4;

    private UiStyle() {}

    public static int toneForVerdict(String verdict) {
        if (verdict == null) return TONE_NEUTRAL;
        switch (verdict.trim()) {
            case "Clean":      return TONE_CLEAN;
            case "Suspicious": return TONE_WARNING;
            case "Malicious":  return TONE_THREAT;
            default:           return TONE_NEUTRAL;
        }
    }

    public static void applyTone(TextView tv, int tone) {
        tv.setBackgroundResource(pillFor(tone));
        tv.setTextColor(ContextCompat.getColor(tv.getContext(), textFor(tone)));
    }

    @DrawableRes
    private static int pillFor(int tone) {
        switch (tone) {
            case TONE_CLEAN:   return R.drawable.bg_pill_clean;
            case TONE_THREAT:  return R.drawable.bg_pill_threat;
            case TONE_WARNING: return R.drawable.bg_pill_warning;
            case TONE_INFO:    return R.drawable.bg_pill_info;
            default:           return R.drawable.bg_pill_neutral;
        }
    }

    @ColorRes
    private static int textFor(int tone) {
        switch (tone) {
            case TONE_CLEAN:   return R.color.status_clean;
            case TONE_THREAT:  return R.color.status_threat;
            case TONE_WARNING: return R.color.status_warning;
            case TONE_INFO:    return R.color.status_info;
            default:           return R.color.status_neutral;
        }
    }
}