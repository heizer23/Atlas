package net.linspad.atlasphone.mobile

import android.content.Context
import net.linspad.atlasphone.mobile.bridge.LoopbackServer
import net.linspad.atlasphone.mobile.bridge.MobileModule
import net.linspad.atlasphone.mobile.bridge.NativeBridge

/**
 * Process-wide holder of the Mobile Platform. Sensor acquisition and buffering live here, not in the
 * Activity, so they survive Activity recreation and web page reloads.
 *
 * The bridge secret and port exist for the lifetime of the process: a re-launch of the TWA inside the
 * same process reuses them, a new process gets a new secret.
 */
object MobilePlatform {
    const val TRUSTED_ORIGIN = "https://workout.linspad.net"

    private var bridge: NativeBridge? = null
    private var server: LoopbackServer? = null
    private var port = 0
    private var token = ""

    /** Starts the bridge once (idempotent). */
    @Synchronized
    fun start(context: Context) {
        if (server != null) return
        val bridge = NativeBridge(modules(context.applicationContext))
        val server = LoopbackServer(
            token = LoopbackServer.newToken().also { token = it },
            allowedOrigin = TRUSTED_ORIGIN,
            onMessage = bridge::onMessage,
            onConnectionChanged = bridge::onConnectionChanged,
        )
        bridge.attachTransport { server.send(it) }
        port = server.start()
        this.bridge = bridge
        this.server = server
    }

    /**
     * URL fragment that hands the web app the bridge endpoint: `#bridge=<port>.<token>`.
     * Fragments are never sent to a server; the page reads and strips it at load.
     */
    @Synchronized
    fun launchFragment(): String = if (server == null) "" else "bridge=$port.$token"

    private fun modules(@Suppress("UNUSED_PARAMETER") appContext: Context): List<MobileModule> = emptyList()
}
