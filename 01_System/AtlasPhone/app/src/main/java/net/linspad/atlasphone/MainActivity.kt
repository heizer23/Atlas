package net.linspad.atlasphone

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import com.google.androidbrowserhelper.trusted.LauncherActivity
import com.google.firebase.messaging.FirebaseMessaging

private const val ATLAS_URL = "https://workout.linspad.net/"
private const val TAG = "MainActivity"

// Launches Atlas as a Trusted Web Activity (full-screen Chrome, no address bar).
// Requires https://workout.linspad.net/.well-known/assetlinks.json to list this
// app's package + signing-cert fingerprint; otherwise Chrome falls back to a Custom Tab.
class MainActivity : LauncherActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        requestNotificationPermissionIfNeeded()
        logFcmToken()
        super.onCreate(savedInstanceState)
    }

    // atlas://workout/123  →  https://workout.linspad.net/workout/123
    override fun getLaunchingUrl(): Uri {
        val uri = intent.data
        if (uri?.scheme == "atlas") {
            return Uri.parse(uri.toString().replaceFirst("atlas://", ATLAS_URL))
        }
        return super.getLaunchingUrl()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 0)
            }
        }
    }

    private fun logFcmToken() {
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            Log.i(TAG, "FCM token: $token")
            AtlasMessagingService.registerToken(this, token)
        }
    }
}
