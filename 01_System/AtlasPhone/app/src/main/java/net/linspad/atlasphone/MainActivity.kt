package net.linspad.atlasphone

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import com.google.firebase.messaging.FirebaseMessaging
import androidx.activity.compose.setContent
import androidx.browser.customtabs.CustomTabColorSchemeParams
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

private const val ATLAS_URL = "https://workout.linspad.net/"
private const val TAG = "MainActivity"

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        logFcmToken()
        handleAtlasIntent(intent)

        setContent {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(text = "AtlasPhone")
                Button(onClick = { openInCustomTab(ATLAS_URL) }) {
                    Text(text = "Open Atlas")
                }
            }
        }
    }

    // Called when the activity is already running and a new atlas:// intent arrives
    // (e.g. user taps a notification while the app is in the foreground).
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleAtlasIntent(intent)
    }

    // Converts an atlas:// deep link to its https:// equivalent and opens it in Custom Tabs.
    // atlas://workout/123  →  https://workout.linspad.net/workout/123
    private fun handleAtlasIntent(intent: Intent) {
        val uri = intent.data ?: return
        if (uri.scheme != "atlas") return
        val webUrl = uri.toString().replaceFirst("atlas://", ATLAS_URL)
        openInCustomTab(webUrl)
    }

    private fun openInCustomTab(url: String) {
        CustomTabsIntent.Builder()
            .setShowTitle(false)
            .setUrlBarHidingEnabled(true)
            .setDefaultColorSchemeParams(
                CustomTabColorSchemeParams.Builder()
                    .setToolbarColor(Color.parseColor("#121212"))
                    .build()
            )
            .build()
            .launchUrl(this, Uri.parse(url))
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
