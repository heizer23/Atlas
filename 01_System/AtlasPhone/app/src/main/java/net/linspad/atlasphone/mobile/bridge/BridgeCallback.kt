package net.linspad.atlasphone.mobile.bridge

import android.net.Uri
import android.os.Bundle
import androidx.browser.customtabs.CustomTabsCallback

/** Routes Custom Tabs session callbacks into the [NativeBridge]. */
class BridgeCallback(private val bridge: NativeBridge) : CustomTabsCallback() {
    override fun onNavigationEvent(navigationEvent: Int, extras: Bundle?) {
        if (navigationEvent == NAVIGATION_FINISHED) bridge.onNavigationFinished()
    }

    override fun onRelationshipValidationResult(relation: Int, requestedOrigin: Uri, result: Boolean, extras: Bundle?) {
        bridge.onRelationshipValidated(relation, requestedOrigin, result)
    }

    override fun onMessageChannelReady(extras: Bundle?) = bridge.onChannelReady()

    override fun onPostMessage(message: String, extras: Bundle?) = bridge.onMessage(message)
}
