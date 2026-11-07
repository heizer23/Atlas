package net.linspad.atlasphone

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import androidx.browser.customtabs.CustomTabsCallback
import androidx.browser.customtabs.CustomTabsSession
import com.google.androidbrowserhelper.trusted.LauncherActivity
import com.google.androidbrowserhelper.trusted.TwaLauncher
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.bridge.BridgeCallback
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

    private var twaLauncher: TwaLauncher? = null

    // Mobile Platform bridge: the TWA session's callbacks carry web <-> native messages.
    override fun getCustomTabsCallback(): CustomTabsCallback = BridgeCallback(MobilePlatform.bridge(this))

    override fun createTwaLauncher(): TwaLauncher = super.createTwaLauncher().also {
        twaLauncher = it
        MobilePlatform.bridge(this).attachSessionSupplier { sessionOf(it) }
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

    // androidbrowserhelper keeps its CustomTabsSession private; the bridge needs it for postMessage.
    // If a library update renames the field the bridge reports itself unavailable instead of crashing.
    private fun sessionOf(launcher: TwaLauncher): CustomTabsSession? = try {
        TwaLauncher::class.java.getDeclaredField("mSession").apply { isAccessible = true }.get(launcher) as? CustomTabsSession
    } catch (e: Exception) {
        Log.e(TAG, "cannot reach TWA session; native bridge disabled", e)
        null
    }
}
