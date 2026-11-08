package net.linspad.atlasphone.mobile.bridge

import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.browser.customtabs.CustomTabsService
import androidx.browser.customtabs.CustomTabsSession
import org.json.JSONObject

private const val TAG = "NativeBridge"

/**
 * Native end of the TWA postMessage channel.
 *
 * Connection model (Chrome Custom Tabs postMessage):
 *  1. Chrome verifies that the page origin trusts this app (Digital Asset Links, relation use_as_origin).
 *  2. We request a message channel for exactly [TRUSTED_ORIGIN]; the page receives a MessagePort.
 *  3. The page sends the first message (`hello`); only then is the bridge "connected".
 *  4. A page reload / navigation drops the channel; we request it again after every navigation.
 *
 * Only [TRUSTED_ORIGIN] is ever granted a channel, so other origins (e.g. an external link opened
 * inside the TWA) can never reach native code.
 */
class NativeBridge(
    private val sourceOrigin: Uri,
    private val modules: List<MobileModule>,
) {
    companion object {
        const val TRUSTED_ORIGIN = "https://workout.linspad.net"
    }

    enum class State { DETACHED, VALIDATING, CHANNEL_REQUESTED, CHANNEL_READY, CONNECTED }

    @Volatile var state: State = State.DETACHED
        private set
    private var session: CustomTabsSession? = null
    private val main = Handler(Looper.getMainLooper())
    private val emitter = BridgeEmitter { name, data -> send(BridgeProtocol.event(name, data)) }

    val bridgeEmitter: BridgeEmitter get() = emitter

    private var sessionSupplier: (() -> CustomTabsSession?)? = null

    /** The session only exists once the TWA has connected, so it is looked up lazily. */
    fun attachSessionSupplier(supplier: () -> CustomTabsSession?) {
        sessionSupplier = supplier
    }

    /**
     * Called right before the TWA intent is launched, while AtlasPhone is still the foreground app.
     * Chrome only accepts channel requests from a foreground caller, so this is the earliest and
     * most reliable moment; later requests (after navigation) are a fallback.
     */
    fun onBeforeLaunch(launchSession: CustomTabsSession) {
        session = launchSession
        Log.i(TAG, "before launch: requesting channel while foreground")
        if (openChannel()) state = State.CHANNEL_REQUESTED
    }

    /** Chrome accepted warmup(): retry the channel request if an earlier one was refused. */
    fun onWarmedUp() {
        Log.i(TAG, "warmup done")
        if (state != State.DETACHED && state != State.VALIDATING) return
        val s = sessionSupplier?.invoke() ?: return
        session = s
        if (openChannel()) state = State.CHANNEL_REQUESTED
    }

    /** Called on every finished navigation: (re)establish the channel. */
    fun onNavigationFinished() {
        val s = sessionSupplier?.invoke()?.also { session = it } ?: return
        if (state == State.CONNECTED) modules.forEach { it.onBridgeDisconnected() }
        state = State.VALIDATING
        val origin = Uri.parse(TRUSTED_ORIGIN)
        val started = try {
            s.validateRelationship(CustomTabsService.RELATION_USE_AS_ORIGIN, origin, null)
        } catch (e: Exception) {
            Log.e(TAG, "validateRelationship threw", e)
            false
        }
        Log.i(TAG, "validateRelationship started=$started")
        if (!started) state = State.DETACHED
    }

    fun onRelationshipValidated(relation: Int, origin: Uri, validated: Boolean) {
        if (relation != CustomTabsService.RELATION_USE_AS_ORIGIN) return
        if (origin.toString().trimEnd('/') != TRUSTED_ORIGIN) return
        if (!validated) {
            Log.w(TAG, "origin not validated: assetlinks.json lacks delegate_permission/common.use_as_origin?")
            state = State.DETACHED
            return
        }
        state = if (openChannel()) State.CHANNEL_REQUESTED else State.DETACHED
    }

    /**
     * Two forms of the request (both target only our origin): with the explicit target origin
     * (newer Chrome) and the classic form. Each outcome is logged to diagnose Chrome support.
     */
    private fun openChannel(): Boolean {
        val target = Uri.parse(TRUSTED_ORIGIN)
        val withTarget = tryRequest("with target origin") {
            // Bundle.EMPTY is immutable and the library putAll()s into it: pass a fresh Bundle.
            requestPostMessageChannel(sourceOrigin, target, Bundle())
        }
        return withTarget || tryRequest("classic") { requestPostMessageChannel(sourceOrigin) }
    }

    private fun tryRequest(label: String, call: CustomTabsSession.() -> Boolean): Boolean {
        val ok = try {
            session?.call() == true
        } catch (e: Exception) {
            Log.e(TAG, "requestPostMessageChannel ($label) threw", e)
            false
        }
        Log.i(TAG, "requestPostMessageChannel ($label) -> $ok")
        return ok
    }

    fun onChannelReady() {
        Log.i(TAG, "message channel ready")
        state = State.CHANNEL_READY
    }

    /** Incoming message from the page. */
    fun onMessage(raw: String) {
        val request = try {
            BridgeProtocol.parseRequest(raw)
        } catch (e: BridgeProtocol.MalformedMessage) {
            Log.w(TAG, "dropped malformed message: ${e.message}")
            return
        }
        state = State.CONNECTED
        val reply = object : Reply {
            override fun ok(result: JSONObject) = send(BridgeProtocol.ok(request.id, result))
            override fun error(code: String, message: String) = send(BridgeProtocol.error(request.id, code, message))
        }
        try {
            dispatch(request, reply)
        } catch (e: Exception) {
            Log.e(TAG, "handler failed", e)
            reply.error(ErrorCodes.INTERNAL, e.message ?: "handler failed")
        }
    }

    private fun dispatch(request: BridgeProtocol.Request, reply: Reply) {
        when (request.method) {
            "hello" -> reply.ok(capabilities().put("protocol", BridgeProtocol.VERSION))
            "ping" -> reply.ok(JSONObject().put("pong", System.currentTimeMillis()))
            "capabilities" -> reply.ok(capabilities())
            else -> {
                val module = modules.firstOrNull { request.method.startsWith(it.name + ".") }
                if (module == null) {
                    reply.error(ErrorCodes.UNKNOWN_METHOD, "unknown method ${request.method}")
                } else {
                    module.handle(request.method.substringAfter('.'), request.params, reply)
                }
            }
        }
    }

    private fun capabilities(): JSONObject {
        val caps = JSONObject()
        modules.forEach { caps.put(it.name, it.describe()) }
        return JSONObject().put("capabilities", caps)
    }

    private fun send(message: String) {
        val s = session
        if (s == null || state < State.CHANNEL_READY) return
        main.post {
            val result = s.postMessage(message, null)
            if (result != CustomTabsService.RESULT_SUCCESS) Log.w(TAG, "postMessage result=$result")
        }
    }
}
