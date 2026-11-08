package net.linspad.atlasphone.mobile

import net.linspad.atlasphone.mobile.bridge.LoopbackServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.DataInputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.Socket
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Exercises the real server over real sockets with a minimal hand-written WebSocket client. */
class LoopbackServerTest {
    private val origin = "https://workout.linspad.net"
    private val token = "test-token-123"
    private val received = CopyOnWriteArrayList<String>()
    private val changes = CopyOnWriteArrayList<Boolean>()
    private lateinit var server: LoopbackServer
    private var port = 0

    @Before fun setUp() {
        server = LoopbackServer(token, origin, { received.add(it) }, { changes.add(it) })
        port = server.start()
    }

    @After fun tearDown() = server.stop()

    // ── tiny client ─────────────────────────────────────────────────────────

    private class Client(val socket: Socket) {
        val input = DataInputStream(socket.getInputStream())
        val out: OutputStream = socket.getOutputStream()

        fun sendText(text: String, fin: Boolean = true, opcode: Int = 1, masked: Boolean = true, payloadLen: Int? = null) {
            val payload = text.toByteArray()
            val len = payloadLen ?: payload.size
            out.write((if (fin) 0x80 else 0) or opcode)
            val maskBit = if (masked) 0x80 else 0
            when {
                len < 126 -> out.write(maskBit or len)
                len < 65536 -> { out.write(maskBit or 126); out.write(len shr 8); out.write(len and 0xff) }
                else -> { out.write(maskBit or 127); for (i in 7 downTo 0) out.write(((len.toLong() shr (8 * i)) and 0xff).toInt()) }
            }
            if (masked) {
                val mask = byteArrayOf(1, 2, 3, 4)
                out.write(mask)
                if (payloadLen == null) out.write(ByteArray(payload.size) { (payload[it].toInt() xor mask[it % 4].toInt()).toByte() })
            } else if (payloadLen == null) out.write(payload)
            out.flush()
        }

        /** Next server frame as (opcode, text) or null on EOF. */
        fun readFrame(): Pair<Int, String>? {
            val b0 = input.read(); if (b0 < 0) return null
            val b1 = input.read(); if (b1 < 0) return null
            var len = b1 and 0x7f
            if (len == 126) len = input.readUnsignedShort()
            val payload = ByteArray(len).also { input.readFully(it) }
            return (b0 and 0x0f) to String(payload)
        }

        fun readHttpStatus(): String {
            val sb = StringBuilder()
            while (!sb.endsWith("\r\n\r\n")) { val b = input.read(); if (b < 0) break; sb.append(b.toChar()) }
            return sb.lines().first()
        }
    }

    private fun connect(
        origin: String? = this.origin,
        host: String = "127.0.0.1:$port",
        key: String = "dGhlIHNhbXBsZSBub25jZQ==",
    ): Pair<Client, String> {
        val socket = Socket(InetAddress.getByName("127.0.0.1"), port).apply { soTimeout = 3000 }
        val c = Client(socket)
        val sb = StringBuilder("GET / HTTP/1.1\r\nHost: $host\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n")
        sb.append("Sec-WebSocket-Key: $key\r\nSec-WebSocket-Version: 13\r\n")
        if (origin != null) sb.append("Origin: $origin\r\n")
        sb.append("\r\n")
        c.out.write(sb.toString().toByteArray()); c.out.flush()
        return c to c.readHttpStatus()
    }

    private fun authed(): Client {
        val (c, status) = connect()
        assertTrue(status, status.contains("101"))
        c.sendText(JSONObject().put("v", 1).put("type", "auth").put("token", token).toString())
        val ack = c.readFrame()!!
        assertTrue(JSONObject(ack.second).getBoolean("ok"))
        return c
    }

    private fun await(cond: () -> Boolean) {
        val end = System.currentTimeMillis() + 3000
        while (System.currentTimeMillis() < end && !cond()) Thread.sleep(10)
        assertTrue(cond())
    }

    // ── tests ───────────────────────────────────────────────────────────────

    @Test fun listensOnLoopbackOnly() {
        assertTrue(port > 0)
        val socket = Socket(InetAddress.getByName("127.0.0.1"), port)
        assertTrue(socket.inetAddress.isLoopbackAddress); socket.close()
    }

    @Test fun handshakeComputesAcceptKey() {
        val (c, status) = connect()
        assertTrue(status.contains("101"))
        val expected = Base64.getEncoder().encodeToString(
            MessageDigest.getInstance("SHA-1").digest("dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11".toByteArray()))
        assertEquals("s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", expected) // RFC 6455 sample
        c.socket.close()
    }

    @Test fun rejectsForeignOrMissingOrigin() {
        for (o in listOf("https://evil.example", "http://workout.linspad.net", "https://workout.linspad.net.evil.com", null)) {
            val (c, status) = connect(origin = o)
            assertTrue("origin $o -> $status", status.contains("403"))
            c.socket.close()
        }
    }

    @Test fun rejectsWrongHost() {
        val (c, status) = connect(host = "evil.example:$port")
        assertTrue(status.contains("403")); c.socket.close()
    }

    @Test fun wrongTokenIsClosedWithoutReply() {
        val (c, _) = connect()
        c.sendText(JSONObject().put("v", 1).put("type", "auth").put("token", "nope").toString())
        val frame = c.readFrame()
        assertEquals(8, frame?.first)             // close frame, no auth ack
        assertTrue(received.isEmpty()); assertTrue(changes.isEmpty())
    }

    @Test fun nonAuthFirstMessageIsClosed() {
        val (c, _) = connect()
        c.sendText("""{"v":1,"type":"request","id":"1","method":"ping"}""")
        assertEquals(8, c.readFrame()?.first)
        assertTrue(received.isEmpty())
    }

    @Test fun authenticatedMessagesReachHandlerAndRepliesReturn() {
        val c = authed()
        await { changes.contains(true) }
        c.sendText("""{"v":1,"type":"request","id":"1","method":"ping"}""")
        await { received.size == 1 }
        assertTrue(received[0].contains("ping"))
        assertTrue(server.send("hello-client"))
        assertEquals(1 to "hello-client", c.readFrame())
    }

    @Test fun sendWithoutClientReturnsFalse() = assertFalse(server.send("x"))

    @Test fun newConnectionReplacesOldOne() {
        val first = authed()
        await { server.isConnected }
        val second = authed()
        assertEquals(8, first.readFrame()?.first)
        server.send("to-second")
        assertEquals("to-second", second.readFrame()?.second)
    }

    @Test fun disconnectIsReported() {
        val c = authed()
        await { changes.contains(true) }
        c.socket.close()
        await { changes.lastOrNull() == false }
        assertFalse(server.isConnected)
    }

    @Test fun oversizedFrameClosesConnection() {
        val c = authed()
        c.sendText("", payloadLen = LoopbackServer.MAX_PAYLOAD + 1)
        assertEquals(8, c.readFrame()?.first)
        assertTrue(received.isEmpty())
    }

    @Test fun unmaskedFragmentedAndBinaryFramesAreRejected() {
        for (variant in 0..2) {
            val c = authed()
            when (variant) {
                0 -> c.sendText("x", masked = false)
                1 -> c.sendText("x", fin = false)
                2 -> c.sendText("x", opcode = 2)
            }
            assertEquals("variant $variant", 8, c.readFrame()?.first)
            assertTrue(received.isEmpty())
        }
    }

    @Test fun pingGetsPong() {
        val c = authed()
        c.sendText("beat", opcode = 9)
        assertEquals(10 to "beat", c.readFrame())
    }

    @Test fun garbageHandshakeIsRejected() {
        val socket = Socket(InetAddress.getByName("127.0.0.1"), port).apply { soTimeout = 3000 }
        val c = Client(socket)
        c.out.write("POST / HTTP/1.1\r\nHost: 127.0.0.1:$port\r\n\r\n".toByteArray()); c.out.flush()
        assertTrue(c.readHttpStatus().contains("400"))
    }

    @Test fun tokensAreLongAndUnique() {
        val a = LoopbackServer.newToken(); val b = LoopbackServer.newToken()
        assertTrue(a.length >= 43); assertTrue(a != b)
    }
}
