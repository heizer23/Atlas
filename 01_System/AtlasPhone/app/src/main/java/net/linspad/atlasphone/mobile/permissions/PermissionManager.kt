package net.linspad.atlasphone.mobile.permissions

import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

/**
 * Central place for the sensor permissions. The Activity shows the system dialog (an Activity is required);
 * this class decides what is needed, remembers that we asked, and derives the status.
 * Nothing here prompts by itself: a request happens only when the user uses the capability, and after a denial
 * only on an explicit retry.
 */
class PermissionManager(private val context: Context) {
    private val prefs = context.getSharedPreferences("mobile_permissions", Context.MODE_PRIVATE)

    fun required(capability: Capability): List<String> = PermissionLogic.required(capability, Build.VERSION.SDK_INT)

    fun toRequest(capability: Capability): List<String> = PermissionLogic.toRequest(capability, Build.VERSION.SDK_INT)

    fun isGranted(capability: Capability): Boolean = required(capability).all {
        ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
    }

    /** Pass the foreground [activity] so "don't ask again" can be told apart from a plain denial. */
    fun status(capability: Capability, activity: Activity?): PermissionStatus {
        val granted = isGranted(capability)
        val asked = prefs.getBoolean(key(capability), false)
        val rationale = activity != null && required(capability).any { activity.shouldShowRequestPermissionRationale(it) }
        // Without an activity we cannot tell DENIED from BLOCKED; report the safer "DENIED" (user can retry/open settings).
        return if (!granted && asked && activity == null) PermissionStatus.DENIED
        else PermissionLogic.status(granted, asked, rationale)
    }

    fun markRequested(capability: Capability) {
        prefs.edit().putBoolean(key(capability), true).apply()
    }

    private fun key(c: Capability) = "asked_${c.name}"
}
