package net.linspad.atlasphone.mobile.bridge

import android.util.Log
import org.json.JSONObject

private const val TAG = "NativeBridge"

/** Carries encoded protocol messages to the web app. */
fun interface BridgeTransport {
    /** @return false if no client is connected. */
    fun send(message: String): Boolean
}

/**
 * Transport-independent core of the native bridge: parses requests, answers the built-in methods
 * (`hello`, `ping`, `capabilities`), routes `<module>.<method>` to the registered [MobileModule]s
 * and lets modules push events. The wire transport is the authenticated [LoopbackServer].
 */
class NativeBridge(private val modules: List<MobileModule>) {
    @Volatile private var transport: BridgeTransport? = null

    /** Lets modules push events to the web app (dropped while no client is connected). */
    val emitter = BridgeEmitter { name, data -> send(BridgeProtocol.event(name, data)) }

    fun attachTransport(transport: BridgeTransport) {
        this.transport = transport
    }

    /** The authenticated client appeared or went away (page load, reload, navigation, crash). */
    fun onConnectionChanged(connected: Boolean) {
        Log.i(TAG, if (connected) "web client connected" else "web client disconnected")
        if (!connected) modules.forEach { it.onBridgeDisconnected() }
    }

    /** Incoming message from the (already authenticated) web client. */
    fun onMessage(raw: String) {
        val request = try {
            BridgeProtocol.parseRequest(raw)
        } catch (e: BridgeProtocol.MalformedMessage) {
            Log.w(TAG, "dropped malformed message: ${e.message}")
            return
        }
        val reply = object : Reply {
            override fun ok(result: JSONObject) { send(BridgeProtocol.ok(request.id, result)) }
            override fun error(code: String, message: String) { send(BridgeProtocol.error(request.id, code, message)) }
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
        transport?.send(message)
    }
}
