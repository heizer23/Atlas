package net.linspad.atlasphone.mobile.diagnostics

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import net.linspad.atlasphone.MainActivity
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.capture.CaptureInfo
import net.linspad.atlasphone.mobile.heartrate.HeartRateMonitor
import net.linspad.atlasphone.mobile.location.TrackingState
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionStatus

/**
 * Technical diagnostic screen for the Mobile Platform (not the RunningTracker UI). Exercises the real native modules:
 * permissions, GPS, Polar H10 / BLE heart rate, and the capture buffer. Opened from the launcher shortcut
 * "Mobile Platform test" (long-press the AtlasPhone icon).
 */
class MobileTestActivity : ComponentActivity() {
    private lateinit var platform: MobilePlatform
    private var pendingAfterGrant: (() -> Unit)? = null

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        platform.log("Permission result: " + result.entries.joinToString { "${it.key.substringAfterLast('.')}=${it.value}" })
        val action = pendingAfterGrant
        pendingAfterGrant = null
        // Continue the user's action only if everything it needs was granted; a denial is never re-prompted automatically.
        if (result.values.all { it }) action?.invoke()
        permissionTick.value = permissionTick.value + 1
    }

    private val permissionTick = mutableStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        platform = MobilePlatform.get(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) // the test is run with the screen on
        setContent { MaterialTheme { Surface { Screen() } } }
    }

    override fun onResume() {
        super.onResume()
        permissionTick.value = permissionTick.value + 1 // permissions may have been changed in system settings
    }

    /** Runs [action] if the capability is permitted; otherwise asks once (first use) or explains how to proceed. */
    private fun withPermission(capability: Capability, explicitRetry: Boolean = false, action: () -> Unit) {
        when (platform.permissions.status(capability, this)) {
            PermissionStatus.GRANTED -> action()
            PermissionStatus.NOT_REQUESTED -> request(capability, action)
            PermissionStatus.DENIED -> if (explicitRetry) request(capability, action) else platform.log("${capability.name} permission was denied — use the Grant button to try again")
            PermissionStatus.BLOCKED -> platform.log("${capability.name} permission is blocked — open the app settings")
        }
    }

    private fun request(capability: Capability, action: () -> Unit) {
        pendingAfterGrant = action
        platform.permissions.markRequested(capability)
        permissionLauncher.launch(platform.permissions.toRequest(capability).toTypedArray())
    }

    private fun openAppSettings() {
        startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null)))
    }

    private fun startGps() = withPermission(Capability.LOCATION) {
        if (platform.location.start()) platform.ensureForegroundService(this)
    }

    private fun scan() = withPermission(Capability.BLUETOOTH) { platform.heartRate.scan() }

    private fun connect(d: HeartRateMonitor.Device) = withPermission(Capability.BLUETOOTH) {
        platform.heartRate.connect(d)
        platform.ensureForegroundService(this)
    }

    private fun connectLast() = withPermission(Capability.BLUETOOTH) {
        platform.heartRate.connectLast()
        platform.ensureForegroundService(this)
    }

    private fun startCapture() {
        val id = platform.recorder.start()
        platform.log("Capture started: $id")
        platform.ensureForegroundService(this)
    }

    // ── UI ────────────────────────────────────────────────────────────────────

    @Composable
    private fun Screen() {
        @Suppress("UNUSED_VARIABLE") val tick by permissionTick // re-read permission status after results
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Mobile Platform test", style = MaterialTheme.typography.headlineSmall)
            DeviceStatus()
            GpsSection()
            HeartRateSection()
            CaptureSection()
            LogSection()
            OutlinedButton(onClick = { startActivity(Intent(this@MobileTestActivity, MainActivity::class.java)); finish() }) {
                Text("Back to Atlas")
            }
        }
    }

    @Composable
    private fun Section(title: String, content: @Composable () -> Unit) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                content()
            }
        }
    }

    @Composable
    private fun DeviceStatus() = Section("Device status") {
        val ble = packageManager.hasSystemFeature(android.content.pm.PackageManager.FEATURE_BLUETOOTH_LE)
        Text("Native platform: running (no web bridge)")
        Text("Capabilities: location = yes, Bluetooth LE heart rate = ${if (ble) "yes" else "NO"}")
        PermissionRow("Location", Capability.LOCATION)
        PermissionRow("Bluetooth", Capability.BLUETOOTH)
    }

    @Composable
    private fun PermissionRow(label: String, capability: Capability) {
        val status = platform.permissions.status(capability, this)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("$label permission: ${status.name.lowercase().replace('_', ' ')}")
            when (status) {
                PermissionStatus.NOT_REQUESTED, PermissionStatus.DENIED ->
                    OutlinedButton(onClick = { withPermission(capability, explicitRetry = true) {} }) { Text("Grant") }
                PermissionStatus.BLOCKED -> OutlinedButton(onClick = { openAppSettings() }) { Text("Settings") }
                PermissionStatus.GRANTED -> Unit
            }
        }
    }

    @Composable
    private fun GpsSection() = Section("GPS") {
        val state by platform.location.state.collectAsState()
        val latest by platform.location.latest.collectAsState()
        val count by platform.location.received.collectAsState()
        Text("State: ${state.name.lowercase().replace('_', ' ')}")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { startGps() }, enabled = !platform.location.isTracking()) { Text("Start") }
            OutlinedButton(onClick = { platform.location.stop() }, enabled = state != TrackingState.IDLE) { Text("Stop") }
        }
        val l = latest
        Text("Latitude / longitude: " + (l?.let { "%.6f, %.6f".format(it.latitude, it.longitude) } ?: "—"))
        Text("Accuracy: " + (l?.accuracyMeters?.let { "%.1f m".format(it) } ?: "—") + "   Speed: " + (l?.speedMetersPerSecond?.let { "%.2f m/s".format(it) } ?: "—"))
        Text("Altitude: " + (l?.altitudeMeters?.let { "%.1f m".format(it) } ?: "—") + "   Bearing: " + (l?.bearingDegrees?.let { "%.0f°".format(it) } ?: "—"))
        Text("Last fix: " + (l?.let { SampleJson.iso(it.timestampMillis) } ?: "—"))
        Text("Samples received: $count")
    }

    @Composable
    private fun HeartRateSection() = Section("Heart rate (Bluetooth)") {
        val state by platform.heartRate.state.collectAsState()
        val devices by platform.heartRate.devices.collectAsState()
        val connected by platform.heartRate.connectedDevice.collectAsState()
        val latest by platform.heartRate.latest.collectAsState()
        val count by platform.heartRate.received.collectAsState()
        val attempt by platform.heartRate.attempt.collectAsState()
        Text("State: ${state.name.lowercase().replace('_', ' ')}" + if (attempt > 0) " (attempt $attempt)" else "")
        Text("Sensor: " + (connected?.let { it.name ?: it.address } ?: "—"))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { scan() }) { Text("Scan") }
            OutlinedButton(onClick = { platform.heartRate.disconnect() }) { Text("Disconnect") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { connectLast() }, enabled = platform.heartRate.lastDeviceAddress() != null) {
                Text("Connect last" + (platform.heartRate.lastDeviceName()?.let { " ($it)" } ?: ""))
            }
            OutlinedButton(onClick = { platform.heartRate.reconnect() }) { Text("Reconnect") }
        }
        devices.forEach { d ->
            OutlinedButton(onClick = { connect(d) }, modifier = Modifier.fillMaxWidth()) {
                Text("${d.name ?: "unnamed"}  ${d.address}  ${d.rssi} dBm")
            }
        }
        Text("Heart rate: " + (latest?.let { "${it.bpm} bpm" } ?: "—"))
        Text("Last reading: " + (latest?.let { SampleJson.iso(it.timestampMillis) } ?: "—"))
        Text("Samples received: $count")
    }

    @Composable
    private fun CaptureSection() = Section("Capture") {
        val active by platform.recorder.active.collectAsState()
        var report by remember { mutableStateOf("") }
        var shown by remember { mutableStateOf<CaptureInfo?>(null) }
        val info = active ?: shown
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { startCapture() }, enabled = active == null) { Text("Start capture") }
            OutlinedButton(onClick = { shown = active; platform.recorder.stop(); shown = shown?.let { platform.store.info(it.id) } }, enabled = active != null) { Text("Stop capture") }
        }
        if (info == null) Text("No capture yet") else {
            Text("Capture ID: ${info.id}")
            Text("Status: ${if (info.isOpen) "recording" else "finished"}   last sequence: ${info.lastSequence}")
            Text("Location samples: ${info.locationCount}   Heart-rate samples: ${info.heartRateCount}")
            Text("Unacknowledged: ${info.unacked}   Dropped (buffer full): ${info.dropped}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { report = platform.store.verifyRetrieval(info.id) }) { Text("Verify retrieval") }
                OutlinedButton(onClick = {
                    val last = info.lastSequence
                    val n = platform.store.ack(info.id, last)
                    val purged = platform.store.purgeAcked(info.id)
                    report = "Acknowledged $n, removed $purged"
                    shown = platform.store.info(info.id)
                }, enabled = !info.isOpen) { Text("Ack + clean") }
            }
            if (report.isNotEmpty()) Text(report)
        }
        val interrupted = remember(active) { platform.store.openCaptures().filter { it.id != active?.id } }
        interrupted.forEach { c ->
            OutlinedButton(onClick = { platform.recorder.start(c.id); platform.ensureForegroundService(this@MobileTestActivity) }, enabled = active == null) {
                Text("Continue interrupted ${c.id.take(8)}… (${c.locationCount + c.heartRateCount} samples)")
            }
        }
        OutlinedButton(onClick = { platform.stopAll() }) { Text("Stop everything") }
    }

    @Composable
    private fun LogSection() = Section("Events and errors") {
        val log by platform.eventLog.collectAsState()
        if (log.isEmpty()) Text("—") else Text(log.take(30).joinToString("\n"), style = MaterialTheme.typography.bodySmall)
    }
}
