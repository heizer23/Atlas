package net.linspad.atlasphone.mobile.bridge

import org.json.JSONObject

/**
 * Wire protocol between the Atlas web app and the native Mobile Platform.
 * Every message is one JSON string (the TWA postMessage channel carries strings).
 *
 *   web -> native  {"v":1,"type":"request","id":"r1","method":"location.start","params":{...}}
 *   native -> web  {"v":1,"type":"response","id":"r1","ok":true,"result":{...}}
 *                  {"v":1,"type":"response","id":"r1","ok":false,"error":{"code":"...","message":"..."}}
 *   native -> web  {"v":1,"type":"event","name":"location.sample","data":{...}}
 *
 * Pure JSON helpers only: no Android dependencies besides org.json, so they are unit-testable.
 */
object BridgeProtocol {
    const val VERSION = 1

    /** A parsed incoming request. */
    data class Request(val id: String, val method: String, val params: JSONObject)

    /** Thrown for malformed incoming messages (they get no reply: there is no id to answer). */
    class MalformedMessage(message: String) : Exception(message)

    fun parseRequest(raw: String): Request {
        val json = try {
            JSONObject(raw)
        } catch (e: Exception) {
            throw MalformedMessage("not JSON")
        }
        if (json.optInt("v", -1) != VERSION) throw MalformedMessage("unsupported protocol version")
        if (json.optString("type") != "request") throw MalformedMessage("not a request")
        val id = json.optString("id")
        val method = json.optString("method")
        if (id.isEmpty() || method.isEmpty()) throw MalformedMessage("missing id or method")
        return Request(id, method, json.optJSONObject("params") ?: JSONObject())
    }

    fun ok(id: String, result: JSONObject = JSONObject()): String =
        base("response").put("id", id).put("ok", true).put("result", result).toString()

    fun error(id: String, code: String, message: String): String =
        base("response").put("id", id).put("ok", false)
            .put("error", JSONObject().put("code", code).put("message", message)).toString()

    fun event(name: String, data: JSONObject): String =
        base("event").put("name", name).put("data", data).toString()

    private fun base(type: String) = JSONObject().put("v", VERSION).put("type", type)
}

/** Stable error codes returned to the web side. */
object ErrorCodes {
    const val UNKNOWN_METHOD = "unknown_method"
    const val INVALID_PARAMS = "invalid_params"
    const val NOT_READY = "not_ready"
    const val INTERNAL = "internal_error"
}
