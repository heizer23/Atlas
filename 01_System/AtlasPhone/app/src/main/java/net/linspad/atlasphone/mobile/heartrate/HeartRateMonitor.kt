package net.linspad.atlasphone.mobile.heartrate

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionManager
import java.util.UUID

/**
 * BLE heart-rate acquisition using the standard Heart Rate Service (0x180D) / Measurement (0x2A37), so any compliant
 * sensor works; the Polar H10 is the first one in use. Plain Android BLE API, no vendor SDK.
 *
 * Lifecycle: scan (auto-stops) -> connect -> notifications. Link loss triggers a bounded reconnect ([ReconnectPolicy]);
 * after the attempts are used up the state is DISCONNECTED and only a manual [reconnect] continues.
 * All state changes happen on the main thread.
 */
@SuppressLint("MissingPermission") // permissions are checked in ensurePermissions() before every BLE call
class HeartRateMonitor(
    context: Context,
    private val permissions: PermissionManager,
    private val log: (String) -> Unit,
    private val policy: ReconnectPolicy = ReconnectPolicy(),
) {
    enum class State { IDLE, SCANNING, CONNECTING, CONNECTED, RECONNECTING, DISCONNECTED, BLUETOOTH_OFF, NO_PERMISSION, UNAVAILABLE, ERROR }

    data class Device(val address: String, val name: String?, val rssi: Int)

    companion object {
        val HEART_RATE_SERVICE: UUID = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
        val HEART_RATE_MEASUREMENT: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
        private val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        private const val SCAN_TIMEOUT_MS = 20_000L
        private const val CONNECT_TIMEOUT_MS = 15_000L
    }

    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private val prefs = appContext.getSharedPreferences("mobile_heartrate", Context.MODE_PRIVATE)
    private val adapter: BluetoothAdapter? = (appContext.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private val _state = MutableStateFlow(State.IDLE)
    val state: StateFlow<State> = _state
    private val _devices = MutableStateFlow<List<Device>>(emptyList())
    val devices: StateFlow<List<Device>> = _devices
    private val _connected = MutableStateFlow<Device?>(null)
    val connectedDevice: StateFlow<Device?> = _connected
    private val _attempt = MutableStateFlow(0)
    /** Current reconnect attempt (0 when not reconnecting). */
    val attempt: StateFlow<Int> = _attempt
    private val _latest = MutableStateFlow<RawHeartRate?>(null)
    val latest: StateFlow<RawHeartRate?> = _latest
    private val _received = MutableStateFlow(0L)
    val received: StateFlow<Long> = _received
    private val _samples = MutableSharedFlow<RawHeartRate>(extraBufferCapacity = 128)
    val samples: SharedFlow<RawHeartRate> = _samples

    private var gatt: BluetoothGatt? = null
    private var targetAddress: String? = null
    private var targetName: String? = null
    private var wantConnected = false
    private var scanning = false
    private var receiverRegistered = false
    private val scanStop = Runnable { stopScan() }
    private val connectTimeout = Runnable { onLinkLost("connect timeout") }

    /** Address of the sensor used last time, if any. */
    fun lastDeviceAddress(): String? = prefs.getString("last_address", null)
    fun lastDeviceName(): String? = prefs.getString("last_name", null)

    fun isActive(): Boolean = _state.value in setOf(State.CONNECTING, State.CONNECTED, State.RECONNECTING)

    // ── scanning ──────────────────────────────────────────────────────────────

    fun scan() {
        post {
            if (!ensureReady()) return@post
            if (scanning) return@post
            _devices.value = emptyList()
            val filter = ScanFilter.Builder().setServiceUuid(ParcelUuid(HEART_RATE_SERVICE)).build()
            val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
            try {
                adapter!!.bluetoothLeScanner.startScan(listOf(filter), settings, scanCallback)
                scanning = true
                if (!isActive()) _state.value = State.SCANNING
                handler.postDelayed(scanStop, SCAN_TIMEOUT_MS)
                log("Scanning for heart-rate sensors")
            } catch (e: Exception) {
                fail("Scan failed: ${e.message}")
            }
        }
    }

    fun stopScan() {
        post {
            handler.removeCallbacks(scanStop)
            if (scanning) {
                runCatching { adapter?.bluetoothLeScanner?.stopScan(scanCallback) }
                scanning = false
                log("Scan stopped")
            }
            if (_state.value == State.SCANNING) _state.value = State.IDLE
        }
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val d = Device(result.device.address, result.scanRecord?.deviceName ?: result.device.name, result.rssi)
            handler.post {
                _devices.value = (_devices.value.filterNot { it.address == d.address } + d).sortedByDescending { it.rssi }
            }
        }

        override fun onScanFailed(errorCode: Int) {
            handler.post { scanning = false; fail("Scan failed (code $errorCode)") }
        }
    }

    // ── connecting ────────────────────────────────────────────────────────────

    fun connect(device: Device) = connect(device.address, device.name)

    fun connect(address: String, name: String? = null) {
        post {
            if (!ensureReady()) return@post
            stopScan()
            targetAddress = address
            targetName = name
            wantConnected = true
            _attempt.value = 0
            prefs.edit().putString("last_address", address).putString("last_name", name).apply()
            openGatt("connecting to ${name ?: address}")
        }
    }

    fun connectLast() {
        lastDeviceAddress()?.let { connect(it, lastDeviceName()) } ?: log("No remembered sensor")
    }

    /** Manual reconnect after the automatic attempts were used up (or after Bluetooth returned). */
    fun reconnect() {
        post {
            val address = targetAddress ?: lastDeviceAddress() ?: return@post log("Nothing to reconnect to")
            if (!ensureReady()) return@post
            wantConnected = true
            targetAddress = address
            _attempt.value = 0
            openGatt("manual reconnect")
        }
    }

    fun disconnect() {
        post {
            wantConnected = false
            handler.removeCallbacksAndMessages(null)
            closeGatt()
            _connected.value = null
            _attempt.value = 0
            if (_state.value != State.BLUETOOTH_OFF) _state.value = State.IDLE
            log("Heart-rate sensor disconnected")
        }
    }

    private fun openGatt(reason: String) {
        closeGatt()
        val address = targetAddress ?: return
        registerReceiverOnce()
        try {
            val remote = adapter!!.getRemoteDevice(address)
            _state.value = if (_attempt.value > 0) State.RECONNECTING else State.CONNECTING
            log(reason)
            gatt = remote.connectGatt(appContext, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
            handler.postDelayed(connectTimeout, CONNECT_TIMEOUT_MS)
        } catch (e: Exception) {
            fail("Connect failed: ${e.message}")
        }
    }

    private fun closeGatt() {
        handler.removeCallbacks(connectTimeout)
        gatt?.let { g -> runCatching { g.disconnect() }; runCatching { g.close() } }
        gatt = null
    }

    private fun onLinkLost(reason: String) {
        handler.removeCallbacks(connectTimeout)
        closeGatt()
        _connected.value = null
        if (!wantConnected) return
        if (adapter?.isEnabled != true) { _state.value = State.BLUETOOTH_OFF; log("Bluetooth is off"); return }
        val next = _attempt.value + 1
        val delay = policy.delayFor(next)
        if (delay == null) {
            _state.value = State.DISCONNECTED
            _attempt.value = 0
            log("Link lost ($reason); gave up after ${policy.maxAttempts} attempts — tap Reconnect")
            return
        }
        _attempt.value = next
        _state.value = State.RECONNECTING
        log("Link lost ($reason); reconnect attempt $next of ${policy.maxAttempts} in ${delay / 1000.0}s")
        handler.postDelayed({ if (wantConnected) openGatt("reconnect attempt $next") }, delay)
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            handler.post {
                if (g !== gatt) { runCatching { g.close() }; return@post }
                when (newState) {
                    BluetoothProfile.STATE_CONNECTED -> g.discoverServices()
                    BluetoothProfile.STATE_DISCONNECTED -> onLinkLost("disconnected (status $status)")
                }
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            handler.post {
                if (g !== gatt) return@post
                val characteristic = g.getService(HEART_RATE_SERVICE)?.getCharacteristic(HEART_RATE_MEASUREMENT)
                val cccd = characteristic?.getDescriptor(CCCD)
                if (status != BluetoothGatt.GATT_SUCCESS || characteristic == null || cccd == null) {
                    wantConnected = false
                    closeGatt()
                    fail("Device has no standard heart-rate service")
                    return@post
                }
                g.setCharacteristicNotification(characteristic, true)
                val ok = if (Build.VERSION.SDK_INT >= 33) {
                    g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE) == android.bluetooth.BluetoothStatusCodes.SUCCESS
                } else {
                    @Suppress("DEPRECATION") run {
                        cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        g.writeDescriptor(cccd)
                    }
                }
                if (!ok) onLinkLost("cannot enable notifications")
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            handler.post {
                if (g !== gatt) return@post
                if (status != BluetoothGatt.GATT_SUCCESS) { onLinkLost("notification setup failed ($status)"); return@post }
                handler.removeCallbacks(connectTimeout)
                _attempt.value = 0
                _connected.value = Device(g.device.address, targetName ?: g.device.name, 0)
                _state.value = State.CONNECTED
                log("Heart-rate sensor connected")
            }
        }

        // API 33+
        override fun onCharacteristicChanged(g: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            handleValue(characteristic, value)
        }

        // API < 33
        @Deprecated("Deprecated in API 33")
        override fun onCharacteristicChanged(g: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION") handleValue(characteristic, characteristic.value)
        }
    }

    private fun handleValue(characteristic: BluetoothGattCharacteristic, value: ByteArray?) {
        if (characteristic.uuid != HEART_RATE_MEASUREMENT) return
        val now = System.currentTimeMillis()
        val parsed = HeartRateParser.parse(value) ?: return
        if (parsed.bpm <= 0) return // 0 = no valid reading yet (e.g. no skin contact); never invent a value
        val sample = RawHeartRate(now, parsed.bpm, parsed.rrIntervalsMs)
        handler.post { _latest.value = sample; _received.value = _received.value + 1 }
        _samples.tryEmit(sample)
    }

    // ── Bluetooth on/off, permissions ─────────────────────────────────────────

    private val stateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            when (intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR)) {
                BluetoothAdapter.STATE_OFF -> handler.post {
                    handler.removeCallbacksAndMessages(null)
                    closeGatt(); _connected.value = null; scanning = false
                    _state.value = State.BLUETOOTH_OFF
                    log("Bluetooth switched off")
                }
                BluetoothAdapter.STATE_ON -> handler.post {
                    log("Bluetooth back on")
                    if (wantConnected) { _attempt.value = 0; openGatt("reconnecting after Bluetooth returned") }
                    else if (_state.value == State.BLUETOOTH_OFF) _state.value = State.IDLE
                }
            }
        }
    }

    private fun registerReceiverOnce() {
        if (receiverRegistered) return
        ContextCompat.registerReceiver(
            appContext, stateReceiver, IntentFilter(BluetoothAdapter.ACTION_STATE_CHANGED), ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        receiverRegistered = true
    }

    private fun ensureReady(): Boolean {
        registerReceiverOnce()
        if (!appContext.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE) || adapter == null) {
            _state.value = State.UNAVAILABLE; log("No Bluetooth LE on this device"); return false
        }
        if (!permissions.isGranted(Capability.BLUETOOTH)) {
            _state.value = State.NO_PERMISSION; log("Bluetooth permission missing"); return false
        }
        if (!adapter.isEnabled) {
            _state.value = State.BLUETOOTH_OFF; log("Bluetooth is off"); return false
        }
        return true
    }

    private fun fail(message: String) {
        _state.value = State.ERROR
        log(message)
    }

    private inline fun post(crossinline block: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) block() else handler.post { block() }
    }
}
