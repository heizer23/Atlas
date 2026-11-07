package net.linspad.atlasphone.mobile.bridge

import org.json.JSONObject

/**
 * A device capability exposed to the web app (location, heart rate, capture, ...).
 * Modules are independent: each owns the methods under its prefix ("location.", "heartRate.").
 * A module never talks to the web app directly; it answers requests and emits events via [BridgeEmitter].
 */
interface MobileModule {
    /** Method prefix without the dot, e.g. "location". */
    val name: String

    /** Static + dynamic capability info for the `capabilities` response. */
    fun describe(): JSONObject

    /** Handle `<name>.<method>`; must call exactly one of reply.ok / reply.error. */
    fun handle(method: String, params: JSONObject, reply: Reply)

    /** Called when the bridge connection is lost or the page is gone; release nothing durable. */
    fun onBridgeDisconnected() {}
}

/** Answer channel for one request. */
interface Reply {
    fun ok(result: JSONObject = JSONObject())
    fun error(code: String, message: String)
}

/** Lets modules push asynchronous events to the web app. */
fun interface BridgeEmitter {
    fun emit(name: String, data: JSONObject)
}
