package net.linspad.atlasphone.mobile

import android.content.Context
import android.net.Uri
import net.linspad.atlasphone.mobile.bridge.MobileModule
import net.linspad.atlasphone.mobile.bridge.NativeBridge

/**
 * Process-wide holder of the Mobile Platform. Sensor acquisition and buffering live here, not in the
 * Activity, so they survive Activity recreation and web page reloads.
 */
object MobilePlatform {
    private var bridge: NativeBridge? = null

    @Synchronized
    fun bridge(context: Context): NativeBridge =
        bridge ?: NativeBridge(
            sourceOrigin = Uri.parse("android-app://" + context.packageName),
            modules = modules(context.applicationContext),
        ).also { bridge = it }

    private fun modules(@Suppress("UNUSED_PARAMETER") appContext: Context): List<MobileModule> = emptyList()
}
