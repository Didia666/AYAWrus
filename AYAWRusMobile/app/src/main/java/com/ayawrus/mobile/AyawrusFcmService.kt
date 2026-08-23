package com.ayawrus.mobile

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class AyawrusFcmService : FirebaseMessagingService() {

    override fun onCreate() {
        super.onCreate()
        // ✅ AUTO-SUBSCRIBE TO TOPIC "malware_alerts"
        // This is ALL that's needed to receive pushes from your backend
        FirebaseMessaging.getInstance().subscribeToTopic("malware_alerts")
            .addOnCompleteListener { task ->
                val msg = if (task.isSuccessful) {
                    "✅ Subscribed to malware_alerts topic"
                } else {
                    "❌ Failed to subscribe to malware_alerts"
                }
                Log.d(TAG, msg)
            }
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        Log.d(TAG, "Got FCM from: ${remoteMessage.from}")

        // Notification payload
        remoteMessage.notification?.let { notif ->
            Log.d(TAG, "Title: ${notif.title}, Body: ${notif.body}")
            showNotification(
                notif.title ?: "AYAWrus Alert",
                notif.body ?: ""
            )
        }

        // Data payload (fallback if notification payload is empty)
        if (remoteMessage.data.isNotEmpty()) {
            val title = remoteMessage.data["title"] ?: "AYAWrus Alert"
            val body = remoteMessage.data["body"] ?: remoteMessage.data["message"] ?: ""
            if (body.isNotEmpty() && remoteMessage.notification == null) {
                showNotification(title, body)
            }
        }
    }

    private fun showNotification(title: String, body: String) {
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
        )

        val channelId = "malware_alerts"    // 👈 MUST MATCH server.py android.channel_id
        val defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val builder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)  // TODO: Replace with your icon
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setSound(defaultSound)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setContentIntent(pendingIntent)

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Android O+ needs notification channel
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Malware Threat Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Real-time malware & suspicious file alerts from AYAWrus"
                enableVibration(true)
                enableLights(true)
            }
            nm.createNotificationChannel(channel)
        }

        nm.notify(System.currentTimeMillis().toInt(), builder.build())
    }

    override fun onNewToken(token: String) {
        Log.d(TAG, "FCM Token: $token")
        // No need to send to server — we use TOPIC subscription
    }

    companion object {
        private const val TAG = "AYAWrus-FCM"
    }
}
