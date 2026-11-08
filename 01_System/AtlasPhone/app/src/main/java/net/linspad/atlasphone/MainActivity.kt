package net.linspad.atlasphone

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import com.google.androidbrowserhelper.trusted.LauncherActivity
import net.linspad.atlasphone.mobile.MobilePlatform
import com.google.firebase.messaging.FirebaseMessaging

private const val ATLAS_URL = "https://workout.linspad.net/"
private const val TAG = "MainActivity"

// Launches Atlas as a Trusted Web Activity (full-screen Chrome, no address bar).
// Requires https://workout.linspad.net/.well-known/assetlinks.json to list this
// app's package + signing-cert fingerprint; otherwise Chrome falls back to a Custom Tab.
class MainActivity : LauncherActivity() {

    // atlas://grant-local-access: a TWA cannot show Chrome's "local network" permission prompt, so this opens
    // the diagnostics page once in a normal Chrome tab (same per-site permission store), where it can be answered.
    private var grantMode = false

    override fun onCreate(savedInstanceState: Bundle?) {
        grantMode = intent?.data?.let { it.scheme == "atlas" && it.host == "grant-local-access" } == true
        requestNotificationPermissionIfNeeded()
        logFcmToken()
        MobilePlatform.start(this)
        super.onCreate(savedInstanceState)
        if (grantMode) {
            openInChromeTab()
            finish()
        }
    }

    override fun launchTwa() {
        if (!grantMode) super.launchTwa()
    }

    private fun openInChromeTab() {
        val url = "${ATLAS_URL}mobile-test#${MobilePlatform.launchFragment()}"
        val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, Uri.parse(url))
            .setPackage("com.android.chrome")
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            startActivity(intent)
        } catch (e: Exception) {
            Log.w(TAG, "cannot open Chrome for permission grant: ${e.message}")
        }
    }

    // atlas://workout/123  →  https://workout.linspad.net/workout/123
    // The launch URL also carries the Mobile Platform bridge endpoint in its fragment (never sent to a server).
    override fun getLaunchingUrl(): Uri {
        val uri = intent.data
        val base = if (uri?.scheme == "atlas") {
            Uri.parse(uri.toString().replaceFirst("atlas://", ATLAS_URL))
        } else {
            super.getLaunchingUrl()
        }
        return base.buildUpon().encodedFragment(MobilePlatform.launchFragment()).build()
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
