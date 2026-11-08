package net.linspad.atlasphone.mobile.bridge

import android.util.Log
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.DataInputStream
import java.io.EOFException
import java.io.IOException
import java.io.OutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import java.util.concurrent.atomic.AtomicBoolean

private const val TAG = "LoopbackServer"
private const val WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

/**
 * Minimal WebSocket (RFC 6455) server that carries the bridge protocol between the Atlas web app
 * (running in Chrome/TWA) and the native Mobile Platform.
 *
 * Security model — the listener is reachable by every app and every web page on the phone, so:
 *  - binds to the loopback interface only (never reachable from the network);
 *  - the HTTP upgrade is rejected unless `Origin` equals [allowedOrigin] (browsers set it and pages
 *    cannot forge it) and `Host` is a loopback name with our port (DNS-rebinding guard);
 *  - the first frame must carry the per-process secret [token]; anything else closes the socket
 *    (policy violation) without revealing why. Comparison is constant time;
 *  - one authenticated connection at a time (a new one replaces the old), bounded frame size,
 *    handshake and auth deadlines, no fragmentation, no binary frames, no extensions.
 * Other apps can open the port and forge headers, but cannot know the token.
 */
class LoopbackServer(
    private val token: String,
    private val allowedOrigin: String,
    private val onMessage: (String) -> Unit,
    private val onConnectionChanged: (connected: Boolean) -> Unit,
) {
    companion object {
        const val MAX_PAYLOAD = 64 * 1024
        const val MAX_HEADER_BYTES = 8 * 1024
        const val HANDSHAKE_TIMEOUT_MS = 5_000
        const val AUTH_TIMEOUT_MS = 5_000

        fun newToken(): String {
            val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
            return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
        }
    }

    private var server: ServerSocket? = null
    private val running = AtomicBoolean(false)
    @Volatile private var current: Connection? = null

    /** Starts listening on a free loopback port and returns it. */
    @Synchronized
    fun start(): Int {
        check(!running.get()) { "already started" }
        val s = ServerSocket(0, 4, InetAddress.getByName("127.0.0.1"))
        server = s
        running.set(true)
        Thread({ acceptLoop(s) }, "atlas-loopback-accept").apply { isDaemon = true }.start()
        Log.i(TAG, "listening on 127.0.0.1:${s.localPort}")
        return s.localPort
    }

    @Synchronized
    fun stop() {
        running.set(false)
        runCatching { server?.close() }
        current?.close(1001)
        server = null
    }

    /** Sends one text message to the authenticated client; false if none is connected. */
    fun send(text: String): Boolean = current?.sendText(text) ?: false

    val isConnected: Boolean get() = current != null

    private fun acceptLoop(s: ServerSocket) {
        while (running.get()) {
            val socket = try {
                s.accept()
            } catch (e: IOException) {
                break
            }
            Thread({ serve(socket, s.localPort) }, "atlas-loopback-conn").apply { isDaemon = true }.start()
        }
    }

    private fun serve(socket: Socket, port: Int) {
        var conn: Connection? = null
        try {
            socket.tcpNoDelay = true
            socket.soTimeout = HANDSHAKE_TIMEOUT_MS
            val input = DataInputStream(BufferedInputStream(socket.getInputStream()))
            val out = socket.getOutputStream()
            Log.i(TAG, "connection from ${socket.inetAddress.hostAddress}")
            if (!handshake(input, out, port)) return

            conn = Connection(socket, out)
            socket.soTimeout = AUTH_TIMEOUT_MS
            val first = conn.readFrame(input) ?: return
            if (!authenticate(first)) { Log.w(TAG, "rejected connection: authentication failed"); conn.close(1008); return }

            socket.soTimeout = 0
            val previous = current
            current = conn
            previous?.close(1000)
            conn.sendText(JSONObject().put("v", BridgeProtocol.VERSION).put("type", "auth").put("ok", true).toString())
            onConnectionChanged(true)
            while (running.get()) {
                val msg = conn.readFrame(input) ?: break
                onMessage(msg)
            }
        } catch (e: SocketTimeoutException) {
            Log.w(TAG, "connection timed out before authentication")
        } catch (e: EOFException) {
            // client went away
        } catch (e: Exception) {
            Log.w(TAG, "connection ended: ${e.javaClass.simpleName}")
        } finally {
            val wasCurrent = current === conn && conn != null
            if (wasCurrent) current = null
            runCatching { socket.close() }
            if (wasCurrent) onConnectionChanged(false)
        }
    }

    private fun authenticate(first: String): Boolean {
        val json = try { JSONObject(first) } catch (e: Exception) { return false }
        if (json.optString("type") != "auth") return false
        val presented = json.optString("token").toByteArray(Charsets.UTF_8)
        return MessageDigest.isEqual(presented, token.toByteArray(Charsets.UTF_8))
    }

    /** Validates the HTTP upgrade request; writes 101 or an error. Returns true on success. */
    private fun handshake(input: DataInputStream, out: OutputStream, port: Int): Boolean {
        val headers = readHeaders(input) ?: return reject(out, "400 Bad Request", "malformed request")
        val request = headers.first
        val h = headers.second
        if (!request.startsWith("GET ") || !request.endsWith(" HTTP/1.1")) return reject(out, "400 Bad Request", "not a GET")
        if (h["upgrade"]?.lowercase() != "websocket" || h["connection"]?.lowercase()?.contains("upgrade") != true ||
            h["sec-websocket-version"] != "13"
        ) return reject(out, "400 Bad Request", "not a websocket upgrade")
        if (h["origin"] != allowedOrigin) return reject(out, "403 Forbidden", "origin '${h["origin"]?.take(80)}'")
        if (h["host"] != "127.0.0.1:$port" && h["host"] != "localhost:$port") return reject(out, "403 Forbidden", "host '${h["host"]?.take(80)}'")
        val key = h["sec-websocket-key"]?.takeIf { it.isNotBlank() && it.length < 64 } ?: return reject(out, "400 Bad Request", "no key")
        val accept = Base64.getEncoder().encodeToString(
            MessageDigest.getInstance("SHA-1").digest((key + WS_GUID).toByteArray(Charsets.US_ASCII)),
        )
        out.write(
            ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                "Sec-WebSocket-Accept: $accept\r\n\r\n").toByteArray(Charsets.US_ASCII),
        )
        out.flush()
        return true
    }

    private fun reject(out: OutputStream, status: String, why: String): Boolean {
        Log.w(TAG, "rejected connection: $why")
        runCatching {
            out.write("HTTP/1.1 $status\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII))
            out.flush()
        }
        return false
    }

    /** Reads request line + headers (lower-cased names). Null if malformed or too large. */
    private fun readHeaders(input: DataInputStream): Pair<String, Map<String, String>>? {
        val buf = StringBuilder()
        while (buf.length < MAX_HEADER_BYTES) {
            val b = input.read()
            if (b < 0) return null
            buf.append(b.toChar())
            if (buf.endsWith("\r\n\r\n")) break
        }
        if (!buf.endsWith("\r\n\r\n")) return null
        val lines = buf.toString().split("\r\n").filter { it.isNotEmpty() }
        val map = HashMap<String, String>()
        for (line in lines.drop(1)) {
            val i = line.indexOf(':')
            if (i <= 0) return null
            map[line.substring(0, i).trim().lowercase()] = line.substring(i + 1).trim()
        }
        return lines.first() to map
    }

    private class Connection(private val socket: Socket, private val out: OutputStream) {
        private val writeLock = Any()

        fun sendText(text: String): Boolean = writeFrame(0x1, text.toByteArray(Charsets.UTF_8))

        fun close(code: Int) {
            writeFrame(0x8, byteArrayOf((code shr 8).toByte(), code.toByte()))
            runCatching { socket.close() }
        }

        private fun writeFrame(opcode: Int, payload: ByteArray): Boolean = synchronized(writeLock) {
            try {
                out.write(0x80 or opcode)
                when {
                    payload.size < 126 -> out.write(payload.size)
                    payload.size < 65536 -> { out.write(126); out.write(payload.size shr 8); out.write(payload.size and 0xff) }
                    else -> { out.write(127); for (i in 7 downTo 0) out.write(((payload.size.toLong() shr (8 * i)) and 0xff).toInt()) }
                }
                out.write(payload)
                out.flush()
                true
            } catch (e: IOException) {
                false
            }
        }

        /** Next complete text message; null when the peer closed or violated the protocol. */
        fun readFrame(input: DataInputStream): String? {
            while (true) {
                val b0 = input.read()
                if (b0 < 0) return null
                val b1 = input.read()
                if (b1 < 0) return null
                val fin = b0 and 0x80 != 0
                val opcode = b0 and 0x0f
                val masked = b1 and 0x80 != 0
                var len = (b1 and 0x7f).toLong()
                if (b0 and 0x70 != 0 || !masked) { close(1002); return null }   // RSV bits / unmasked client frame
                if (len == 126L) len = input.readUnsignedShort().toLong()
                else if (len == 127L) len = input.readLong()
                if (len < 0 || len > MAX_PAYLOAD) { close(1009); return null }
                val mask = ByteArray(4).also { input.readFully(it) }
                val payload = ByteArray(len.toInt()).also { input.readFully(it) }
                for (i in payload.indices) payload[i] = (payload[i].toInt() xor mask[i % 4].toInt()).toByte()
                when (opcode) {
                    0x1 -> {
                        if (!fin) { close(1003); return null }                 // no fragmentation
                        return String(payload, Charsets.UTF_8)
                    }
                    0x8 -> { close(1000); return null }
                    0x9 -> writeFrame(0xA, payload)
                    0xA -> Unit
                    else -> { close(1003); return null }                       // binary / continuation / unknown
                }
            }
        }
    }
}
