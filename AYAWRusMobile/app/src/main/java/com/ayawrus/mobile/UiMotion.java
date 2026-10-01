package com.ayawrus.mobile;

import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.view.animation.AnimationUtils;
import android.view.animation.DecelerateInterpolator;
import android.widget.TextView;

import androidx.recyclerview.widget.RecyclerView;

public final class UiMotion {

    public static final boolean MOTION_ENABLED = true;
    public static final boolean PULSE_ENABLED = true;

    public static final long COUNT_UP_MS = 700L;
    public static final long FADE_IN_MS = 260L;
    public static final float FADE_IN_START_ALPHA = 0.35f;

    // One half-cycle; a full breath is 2x this (2.5s)
    public static final long PULSE_HALF_CYCLE_MS = 1250L;
    public static final float PULSE_MIN_ALPHA = 0.25f;
    public static final float PULSE_MAX_ALPHA = 1.0f;

    private UiMotion() {}

    /** Slides list items in. Call once per list, right after the first data load. */
    public static void playListEntrance(RecyclerView rv) {
        if (!MOTION_ENABLED || rv == null) return;
        rv.setLayoutAnimation(
                AnimationUtils.loadLayoutAnimation(rv.getContext(), R.anim.layout_list_enter));
        rv.scheduleLayoutAnimation();
    }

    /** Counts from whatever the TextView currently shows up to target. No-op animation if unchanged. */
    public static void animateCount(TextView tv, int target) {
        if (tv == null) return;
        Object old = tv.getTag();
        if (old instanceof ValueAnimator) {
            ((ValueAnimator) old).cancel();
        }
        int from = parseOrZero(tv.getText());
        if (!MOTION_ENABLED || from == target) {
            tv.setText(String.valueOf(target));
            tv.setTag(null);
            return;
        }
        ValueAnimator a = ValueAnimator.ofInt(from, target);
        a.setDuration(COUNT_UP_MS);
        a.setInterpolator(new DecelerateInterpolator());
        a.addUpdateListener(v -> tv.setText(String.valueOf((int) v.getAnimatedValue())));
        tv.setTag(a);
        a.start();
    }

    /** Quick fade-in, used when the banner state changes. */
    public static void fadeIn(View v) {
        if (!MOTION_ENABLED || v == null) return;
        v.setAlpha(FADE_IN_START_ALPHA);
        v.animate().alpha(1f).setDuration(FADE_IN_MS).start();
    }

    /** Slow breathing on a glow overlay. Only animates alpha, so it's cheap. */
    public static void startPulse(View glow) {
        if (!MOTION_ENABLED || !PULSE_ENABLED || glow == null) return;
        Object old = glow.getTag();
        if (old instanceof ObjectAnimator && ((ObjectAnimator) old).isRunning()) return;
        ObjectAnimator a = ObjectAnimator.ofFloat(glow, View.ALPHA, PULSE_MIN_ALPHA, PULSE_MAX_ALPHA);
        a.setDuration(PULSE_HALF_CYCLE_MS);
        a.setRepeatCount(ValueAnimator.INFINITE);
        a.setRepeatMode(ValueAnimator.REVERSE);
        a.setInterpolator(new AccelerateDecelerateInterpolator());
        glow.setTag(a);
        a.start();
    }

    public static void stopPulse(View glow) {
        if (glow == null) return;
        Object old = glow.getTag();
        if (old instanceof ObjectAnimator) {
            ((ObjectAnimator) old).cancel();
        }
        glow.setTag(null);
        glow.setAlpha(0f);
    }

    private static int parseOrZero(CharSequence text) {
        try {
            return Integer.parseInt(text.toString().trim());
        } catch (Exception e) {
            return 0;
        }
    }
}