package net.linspad.atlasphone

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "AtlasMessaging"
private const val CHANNEL_ID = "atlas_platform"
private const val CHANNEL_NAME = "Atlas Notifications"
private const val REGISTER_URL = "https://workout.linspad.net/api/devices/token"

class AtlasMessagingService : FirebaseMessagingService() {

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_HIGH)
        )
    }

    // Called when FCM issues or rotates the registration token.
    // Automatically registers the new token with the Atlas notifications service.
    override fun onNewToken(token: String) {
        Log.i(TAG, "FCM token updated — registering with Atlas")
        getSharedPreferences("atlas_prefs", MODE_PRIVATE)
            .edit().putString("fcm_token", token).apply()
        registerTokenWithAtlas(token)
    }

    private fun registerTokenWithAtlas(token: String) {
        registerToken(this, token)
    }

    companion object {
        fun registerToken(context: android.content.Context, token: String) {
            Thread {
                try {
                    val conn = URL(REGISTER_URL).openConnection() as HttpURLConnection
                    conn.requestMethod = "POST"
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.doOutput = true
                    conn.connectTimeout = 10_000
                    conn.readTimeout = 10_000
                    OutputStreamWriter(conn.outputStream).use { it.write("""{"token":"$token"}""") }
                    val code = conn.responseCode
                    if (code == 200) {
                        Log.i(TAG, "FCM token registered with Atlas (device_id=default)")
                    } else {
                        Log.w(TAG, "Atlas device registration returned HTTP $code")
                    }
                    conn.disconnect()
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to register FCM token with Atlas: $e")
                }
            }.start()
        }
    }

    // All Atlas notifications are data-only (no FCM notification object),
    // so this is called regardless of whether the app is in the foreground or background.
    override fun onMessageReceived(message: RemoteMessage) {
        val data     = message.data
        val title    = data["title"]           ?: return
        val body     = data["body"]            ?: return
        val label    = data["label"]           ?: ""
        val deepLink = data["deep_link"]       ?: ""
        val notifId  = data["notification_id"]?.hashCode() ?: CHANNEL_ID.hashCode()

        val tapIntent = Intent(Intent.ACTION_VIEW, Uri.parse(deepLink), this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)

        val pendingIntent = PendingIntent.getActivity(
            this, notifId, tapIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setSubText(label)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
            .notify(notifId, notification)
    }
}
