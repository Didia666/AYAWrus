package com.ayawrus.mobile

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.ActionBarDrawerToggle
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.fragment.app.Fragment
import com.google.android.material.navigation.NavigationView
import com.google.firebase.messaging.FirebaseMessaging
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity() {

    private lateinit var drawerLayout: DrawerLayout
    private val handler = Handler(Looper.getMainLooper())

    @Volatile
    private var lastAlertTimestamp: Long = 0

    @Volatile
    private var uiRefreshCounter: Int = 0

    private var currentDashboard: DashboardFragment? = null
    private var currentHistory: HistoryFragment? = null
    private var currentQuarantine: QuarantineFragment? = null

    private val alertPollRunnable = object : Runnable {
        override fun run() {
            try {
                Log.d("AYAWrusMain", "[poll-runnable] Woke up, will poll now")
                pollLatestAlert()
            } catch (t: Throwable) {
                Log.e("AYAWrusMain", "[poll-runnable] Unexpected error", t)
            } finally {
                handler.postDelayed(this, POLL_INTERVAL_MS)
            }
        }
    }

    private val requestPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (!isGranted) {
                Log.w("AYAWrusMain", "Notification permission denied by user")
            } else {
                Log.i("AYAWrusMain", "Notification permission granted")
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        try {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(
                androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO
            )
        } catch (t: Throwable) {
            android.util.Log.w("AYAWrusMain", "[theme] Failed to force MODE_NIGHT_NO: ${t.message}")
        }

        super.onCreate(savedInstanceState)
        Log.i("AYAWrusMain", "[onCreate] START")

        try {
            setContentView(R.layout.activity_main)
            try {
                window.setBackgroundDrawableResource(android.R.color.white)
                findViewById<android.view.View>(android.R.id.content)?.setBackgroundColor(0xFFFFFFFF.toInt())
                window.decorView.setBackgroundColor(0xFFFFFFFF.toInt())
            } catch (t: Throwable) {
                Log.w("AYAWrusMain", "[onCreate] decor/screen background override skipped (non-fatal): ${t.message}")
            }
            Log.i("AYAWrusMain", "[onCreate] setContentView ok")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[onCreate] setContentView FAILED", t)
            return
        }

        try {
            createAlertNotificationChannel()
            Log.i("AYAWrusMain", "[onCreate] notification channel ensured")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[onCreate] channel create failed", t)
        }

        try {
            askNotificationPermission()
            Log.i("AYAWrusMain", "[onCreate] permission asked")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[onCreate] permission ask failed", t)
        }

        // Schedule alert polling FIRST (before Firebase) so notifications always work,
        // even if Firebase token fetch crashes the SDK internals.
        try {
            Log.i("AYAWrusMain", "[onCreate] Scheduling alert poll (every ${POLL_INTERVAL_MS}ms)...")
            handler.postDelayed(alertPollRunnable, 3000L)
            handler.postDelayed(alertPollRunnable, 1L)
            Log.i("AYAWrusMain", "[onCreate] Alert poll scheduled.")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[onCreate] FAILED to schedule polling", t)
        }

        try {
            setupDrawerAndFragments(savedInstanceState)
            Log.i("AYAWrusMain", "[onCreate] drawer/fragments ready")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[onCreate] drawer/fragments FAILED", t)
        }

        // Fire and forget FCM token + topic subscription — swallow ALL errors
        try {
            Log.i("AYAWrusMain", "[onCreate] kicking off Firebase init (best-effort)")
            registerDeviceTokenAndSubscribeTopic()
        } catch (t: Throwable) {
            Log.w("AYAWrusMain", "[onCreate] Firebase init blocked (no-op): ${t.message}")
        }

        Log.i("AYAWrusMain", "[onCreate] END — app is fully initialized")
    }

    override fun onDestroy() {
        try {
            handler.removeCallbacks(alertPollRunnable)
        } catch (_: Throwable) {}
        super.onDestroy()
    }

    private fun setupDrawerAndFragments(savedInstanceState: Bundle?) {
        try {
            val toolbar: Toolbar = findViewById(R.id.toolbar)
            try {
                setSupportActionBar(toolbar)
                Log.d("AYAWrusMain", "[UI] setSupportActionBar OK")
            } catch (t: Throwable) {
                Log.w("AYAWrusMain", "[UI] setSupportActionBar skipped (non-fatal): ${t.message}")
            }

            drawerLayout = findViewById(R.id.drawerLayout)
            val navigationView: NavigationView = findViewById(R.id.navigationView)

            try {
                val toggle = ActionBarDrawerToggle(
                    this, drawerLayout, toolbar,
                    R.string.drawer_open,
                    R.string.drawer_close
                )
                drawerLayout.addDrawerListener(toggle)
                toggle.syncState()
                Log.d("AYAWrusMain", "[UI] drawer toggle OK")
            } catch (t: Throwable) {
                Log.w("AYAWrusMain", "[UI] drawer toggle skipped (non-fatal): ${t.message}")
            }

            navigationView.setNavigationItemSelectedListener { item ->
                var selectedFragment: Fragment? = null
                when (item.itemId) {
                    R.id.nav_dashboard -> {
                        val newDash = DashboardFragment()
                        currentDashboard = newDash
                        currentHistory = null
                        currentQuarantine = null
                        selectedFragment = newDash
                        setTitleCompat("Dashboard")
                    }
                    R.id.nav_history -> {
                        val newHist = HistoryFragment()
                        currentHistory = newHist
                        currentDashboard = null
                        currentQuarantine = null
                        selectedFragment = newHist
                        setTitleCompat("History")
                    }
                    R.id.nav_quarantine -> {
                        val newQ = QuarantineFragment()
                        currentQuarantine = newQ
                        currentDashboard = null
                        currentHistory = null
                        selectedFragment = newQ
                        setTitleCompat("Remote Quarantine")
                    }
                }
                selectedFragment?.let {
                    try {
                        supportFragmentManager.beginTransaction()
                            .replace(R.id.fragmentContainer, it)
                            .commit()
                    } catch (t: Throwable) {
                        Log.e("AYAWrusMain", "[UI] nav commit failed", t)
                    }
                }
                try {
                    drawerLayout.closeDrawers()
                } catch (_: Throwable) {}
                true
            }

            if (savedInstanceState == null) {
                try {
                    val dash = DashboardFragment()
                    currentDashboard = dash
                    currentHistory = null
                    currentQuarantine = null
                    supportFragmentManager.beginTransaction()
                        .replace(R.id.fragmentContainer, dash)
                        .commit()
                    setTitleCompat("Dashboard")
                    Log.i("AYAWrusMain", "[UI] DashboardFragment committed")
                } catch (t: Throwable) {
                    Log.e("AYAWrusMain", "[UI] Dashboard fragment commit FAILED", t)
                }
            }
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "[UI] setupDrawerAndFragments top-level crash", t)
        }
    }

    private fun setTitleCompat(titleStr: String) {
        try {
            supportActionBar?.title = titleStr
        } catch (_: Throwable) {
            try {
                actionBar?.title = titleStr
            } catch (_: Throwable) {
                try {
                    setTitle(titleStr)
                } catch (_: Throwable) {}
            }
        }
    }

    private fun refreshCurrentFragmentUi() {
        try {
            val dash = currentDashboard
            if (dash != null && dash.isAdded) {
                dash.refresh()
                Log.i("AYAWrusMain", "[UI-refresh] DashboardFragment.refresh() called")
            }
            val hist = currentHistory
            if (hist != null && hist.isAdded) {
                hist.refresh()
                Log.i("AYAWrusMain", "[UI-refresh] HistoryFragment.refresh() called")
            }
            val q = currentQuarantine
            if (q != null && q.isAdded) {
                q.refresh()
                Log.i("AYAWrusMain", "[UI-refresh] QuarantineFragment.refresh() called")
            }
        } catch (t: Throwable) {
            Log.w("AYAWrusMain", "[UI-refresh] Failed: ${t.message}")
        }
    }

    private fun askNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                Log.i("AYAWrusMain", "POST_NOTIFICATIONS already granted")
            }
        }
    }

    private fun createAlertNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val existing = nm.getNotificationChannel("malware_alerts")
            if (existing == null) {
                val channel = NotificationChannel(
                    "malware_alerts",
                    "Malware Threat Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Real-time malware & suspicious file alerts from AYAWrus"
                    enableVibration(true)
                    enableLights(true)
                }
                nm.createNotificationChannel(channel)
                Log.i("AYAWrusMain", "Created malware_alerts notification channel")
            } else {
                Log.d("AYAWrusMain", "malware_alerts channel already exists")
            }
        }
    }

    private fun showLocalNotification(title: String, body: String) {
        try {
            val intent = Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            }
            val pendingIntent = PendingIntent.getActivity(
                this, 0, intent,
                PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
            )
            val defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val builder = NotificationCompat.Builder(this, "malware_alerts")
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setSound(defaultSound)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setContentIntent(pendingIntent)
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(System.currentTimeMillis().toInt(), builder.build())
            Log.i("AYAWrusMain", "showLocalNotification posted: title=$title")
        } catch (t: Throwable) {
            Log.e("AYAWrusMain", "showLocalNotification FAILED", t)
        }
    }

    private fun pollLatestAlert() {
        val urlsToTry = listOf(
            ApiClient.BASE_URL + "api/alerts/latest",
            "http://10.0.2.2:5000/api/alerts/latest",
            "http://127.0.0.1:5000/api/alerts/latest"
        )
        Thread {
            var anySuccess = false
            var triggeredNewAlert = false
            for (urlStr in urlsToTry) {
                try {
                    Log.d("AYAWrusMain", "[poll] Trying $urlStr")
                    val url = URL(urlStr)
                    val conn = url.openConnection() as HttpURLConnection
                    conn.requestMethod = "GET"
                    conn.connectTimeout = 3500
                    conn.readTimeout = 3500
                    val code = conn.responseCode
                    Log.d("AYAWrusMain", "[poll] $urlStr -> HTTP $code")
                    if (code == 200) {
                        val body = conn.inputStream.bufferedReader().use { it.readText() }
                        Log.v("AYAWrusMain", "[poll] body length=${body.length}")
                        val json = JSONObject(body)
                        if (!json.isNull("alert")) {
                            val alert = json.getJSONObject("alert")
                            val ts = alert.optLong("timestamp", 0L)
                            val title = alert.optString("title", "AYAWrus Alert")
                            val msg = alert.optString("body", "")
                            val fileName = alert.optString("fileName", "")
                            if (lastAlertTimestamp == 0L) {
                                lastAlertTimestamp = ts
                                Log.i(
                                    "AYAWrusMain",
                                    "[poll] FIRST-POLL CAUGHT UP: file=$fileName ts=$ts title=$title"
                                )
                            } else if (ts > lastAlertTimestamp && msg.isNotEmpty()) {
                                runOnUiThread { showLocalNotification(title, msg) }
                                lastAlertTimestamp = ts  
                                triggeredNewAlert = true
                                Log.i(
                                    "AYAWrusMain",
                                    "[poll] NEW ALERT NOTIFIED: $title | $msg"
                                )
                            } else {
                                Log.d(
                                    "AYAWrusMain",
                                    "[poll] No new alert (last=$lastAlertTimestamp current=$ts)"
                                )
                            }
                        } else {
                            if (lastAlertTimestamp == 0L) {
                                Log.d("AYAWrusMain", "[poll] No alerts queued on server yet")
                                lastAlertTimestamp = 1L
                            } else {
                                Log.d("AYAWrusMain", "[poll] Server has no alerts queued")
                            }
                        }
                        anySuccess = true
                        break
                    }
                } catch (e: Exception) {
                    Log.w("AYAWrusMain", "[poll] $urlStr failed: ${e.javaClass.simpleName} -> ${e.message}")
                }
            }
            if (!anySuccess) {
                Log.w("AYAWrusMain", "[poll] ALL urls failed. Is the API server running on the PC? Is firewall on?")
            }

            uiRefreshCounter += 1
            val doPeriodicRefresh = (uiRefreshCounter % UI_REFRESH_EVERY_N_POLLS == 0)
            if (triggeredNewAlert || doPeriodicRefresh) {
                Log.i(
                    "AYAWrusMain",
                    "[poll] scheduling UI refresh. reason=" +
                        (if (triggeredNewAlert) "NEW_ALERT" else "PERIODIC(#$uiRefreshCounter)")
                )
                runOnUiThread { refreshCurrentFragmentUi() }
            }
        }.apply {
            name = "AYAWrus-AlertPoll"
            isDaemon = true
        }.start()
    }

    private fun registerDeviceTokenAndSubscribeTopic() {
        try {
            FirebaseMessaging.getInstance().subscribeToTopic("malware_alerts")
                .addOnCompleteListener { task ->
                    if (task.isSuccessful) {
                        Log.i("AYAWrusMain", "Firebase: subscribed to 'malware_alerts' topic")
                    } else {
                        Log.w("AYAWrusMain", "Firebase: topic subscribe failed", task.exception)
                    }
                }
        } catch (t: Throwable) {
            Log.w("AYAWrusMain", "Firebase topic subscribe exception (ignored): ${t.message}")
        }

        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (!task.isSuccessful) {
                    Log.w("AYAWrusMain", "Firebase: token fetch failed (non-fatal)", task.exception)
                    return@addOnCompleteListener
                }
                val token = task.result
                Log.d("AYAWrusMain", "Firebase: FCM token acquired (len=${token.length})")

                val deviceName = Build.MODEL
                val registration = MalwareApiService.DeviceRegistration(token, deviceName)
                ApiClient.getService().registerDevice(registration)
                    .enqueue(object : retrofit2.Callback<Void> {
                        override fun onResponse(
                            call: retrofit2.Call<Void>,
                            response: retrofit2.Response<Void>
                        ) {
                            if (response.isSuccessful) {
                                Log.d("AYAWrusMain", "Firebase: token registered with backend")
                            } else {
                                Log.w("AYAWrusMain", "Firebase: backend register returned ${response.code()}")
                            }
                        }

                        override fun onFailure(call: retrofit2.Call<Void>, t: Throwable) {
                            Log.w("AYAWrusMain", "Firebase: backend register failed: ${t.message}")
                        }
                    })
            }
        } catch (t: Throwable) {
            Log.w("AYAWrusMain", "Firebase: token fetch exception (ignored): ${t.message}")
        }
    }

    companion object {
        private const val POLL_INTERVAL_MS = 6000L
        private const val UI_REFRESH_EVERY_N_POLLS = 5
    }
}
