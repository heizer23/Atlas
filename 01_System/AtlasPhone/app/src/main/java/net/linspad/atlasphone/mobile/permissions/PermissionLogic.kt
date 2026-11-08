package net.linspad.atlasphone.mobile.permissions

enum class Capability { LOCATION, BLUETOOTH }

/**
 * GRANTED       - usable.
 * NOT_REQUESTED - never asked; first use of the capability triggers the request.
 * DENIED        - user said no; we do NOT prompt again by ourselves, only on an explicit retry.
 * BLOCKED       - "don't ask again" or policy; only the system settings can change it.
 */
enum class PermissionStatus { GRANTED, NOT_REQUESTED, DENIED, BLOCKED }

object PermissionLogic {
    const val FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
    const val COARSE_LOCATION = "android.permission.ACCESS_COARSE_LOCATION"
    const val BLUETOOTH_SCAN = "android.permission.BLUETOOTH_SCAN"
    const val BLUETOOTH_CONNECT = "android.permission.BLUETOOTH_CONNECT"

    /** Permissions that must be granted for [capability] on the given Android SDK level. */
    fun required(capability: Capability, sdk: Int): List<String> = when (capability) {
        Capability.LOCATION -> listOf(FINE_LOCATION)
        // Android 12+: dedicated Bluetooth permissions. Before: BLE scanning needs location.
        Capability.BLUETOOTH -> if (sdk >= 31) listOf(BLUETOOTH_SCAN, BLUETOOTH_CONNECT) else listOf(FINE_LOCATION)
    }

    /** Permissions to put into the system dialog (location also asks for coarse, as Android 12+ requires). */
    fun toRequest(capability: Capability, sdk: Int): List<String> = when (capability) {
        Capability.LOCATION -> listOf(FINE_LOCATION, COARSE_LOCATION)
        else -> required(capability, sdk)
    }

    fun status(allGranted: Boolean, askedBefore: Boolean, shouldShowRationale: Boolean): PermissionStatus = when {
        allGranted -> PermissionStatus.GRANTED
        !askedBefore -> PermissionStatus.NOT_REQUESTED
        shouldShowRationale -> PermissionStatus.DENIED
        else -> PermissionStatus.BLOCKED
    }
}
