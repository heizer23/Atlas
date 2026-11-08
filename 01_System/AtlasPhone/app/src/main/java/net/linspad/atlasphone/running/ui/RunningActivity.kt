package net.linspad.atlasphone.running.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionStatus
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.session.RunController
import net.linspad.atlasphone.running.sync.UploadScheduler

private enum class Page { HOME, PAIRING, SUMMARY }

/**
 * Compose host of the Running Screen (not exported; reached from the launcher shortcut). Keeps the screen on,
 * requests sensor permissions with the same pattern as MobileTestActivity, hosts pairing, the run screens and the
 * summary. Does not touch MainActivity (TWA) or the FCM service.
 */
class RunningActivity : ComponentActivity() {
    private lateinit var platform: MobilePlatform
    private lateinit var controller: RunController
    private var pendingAfterGrant: (() -> Unit)? = null
    private val permissionTick = mutableStateOf(0)

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        platform.log("Permission result: " + result.entries.joinToString { "${it.key.substringAfterLast('.')}=${it.value}" })
        val action = pendingAfterGrant
        pendingAfterGrant = null
        if (result.values.all { it }) action?.invoke() // a denial is never re-prompted automatically
        permissionTick.value = permissionTick.value + 1
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        platform = MobilePlatform.get(this)
        controller = RunController.get(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        UploadScheduler.enqueueAllPending(this) // retry anything still waiting for Atlas
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(background = Color.Black, surface = Color.Black, onSurface = Color.White, onBackground = Color.White, primary = Color(0xFF8CFF66), onPrimary = Color.Black)) {
                Surface(Modifier.fillMaxSize(), color = Color.Black) { RunningApp() }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        permissionTick.value = permissionTick.value + 1 // permissions may have changed in system settings
    }

    /** Runs [action] if the capability is permitted; asks once on first use, otherwise explains via the event log. */
    private fun withPermission(capability: Capability, explicitRetry: Boolean = false, action: () -> Unit) {
        when (platform.permissions.status(capability, this)) {
            PermissionStatus.GRANTED -> action()
            PermissionStatus.NOT_REQUESTED -> request(capability, action)
            PermissionStatus.DENIED -> if (explicitRetry) request(capability, action) else platform.log("${capability.name} permission denied")
            PermissionStatus.BLOCKED -> {
                platform.log("${capability.name} permission is blocked; opening app settings")
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null)))
            }
        }
    }

    private fun request(capability: Capability, action: () -> Unit) {
        pendingAfterGrant = action
        platform.permissions.markRequested(capability)
        permissionLauncher.launch(platform.permissions.toRequest(capability).toTypedArray())
    }

    @Composable
    private fun RunningApp() {
        @Suppress("UNUSED_VARIABLE") val tick by permissionTick
        var page by remember { mutableStateOf(if (controller.tokens.isPaired()) Page.HOME else Page.PAIRING) }
        var summary by remember { mutableStateOf<RunMeta?>(null) }
        when (page) {
            Page.PAIRING -> PairingScreen(onPaired = { page = Page.HOME }, onSkip = { page = Page.HOME })
            Page.SUMMARY -> summary?.let { SummaryScreen(it, onDone = { page = Page.HOME }) } ?: run { page = Page.HOME }
            Page.HOME -> RunningScreen(
                controller = controller,
                ensurePermission = { capability, action -> withPermission(capability, explicitRetry = true, action = action) },
                onFinished = { summary = it; page = Page.SUMMARY },
                onPair = { page = Page.PAIRING },
            )
        }
    }
}
