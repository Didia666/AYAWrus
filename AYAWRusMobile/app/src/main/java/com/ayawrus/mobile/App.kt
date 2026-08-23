package com.ayawrus.mobile

import android.app.Application
import android.util.Log
import androidx.appcompat.app.AppCompatDelegate

class App : Application() {

    override fun onCreate() {
        super.onCreate()

        try {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
            Log.i("AYAWrus-App", "AppCompatDelegate forced MODE_NIGHT_NO globally (process-early)")
        } catch (t: Throwable) {
            Log.w("AYAWrus-App", "Failed to set night mode early: ${t.message}")
        }
    }
}
