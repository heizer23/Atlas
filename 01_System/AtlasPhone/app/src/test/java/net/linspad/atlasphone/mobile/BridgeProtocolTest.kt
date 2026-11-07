package net.linspad.atlasphone.mobile

import net.linspad.atlasphone.mobile.bridge.BridgeProtocol
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class BridgeProtocolTest {
    @Test fun parsesValidRequest() {
        val r = BridgeProtocol.parseRequest("""{"v":1,"type":"request","id":"r1","method":"location.start","params":{"a":1}}""")
        assertEquals("r1", r.id)
        assertEquals("location.start", r.method)
        assertEquals(1, r.params.getInt("a"))
    }

    @Test fun missingParamsBecomeEmptyObject() {
        val r = BridgeProtocol.parseRequest("""{"v":1,"type":"request","id":"r1","method":"ping"}""")
        assertEquals(0, r.params.length())
    }

    @Test fun rejectsMalformed() {
        listOf(
            "nope", """{"v":2,"type":"request","id":"a","method":"m"}""",
            """{"v":1,"type":"event","id":"a","method":"m"}""", """{"v":1,"type":"request","method":"m"}""",
            """{"v":1,"type":"request","id":"a"}""",
        ).forEach {
            try {
                BridgeProtocol.parseRequest(it); fail("accepted: $it")
            } catch (_: BridgeProtocol.MalformedMessage) {
            }
        }
    }

    @Test fun responsesCarryIdAndStatus() {
        val ok = JSONObject(BridgeProtocol.ok("r1", JSONObject().put("x", 2)))
        assertTrue(ok.getBoolean("ok")); assertEquals("r1", ok.getString("id")); assertEquals(2, ok.getJSONObject("result").getInt("x"))
        val err = JSONObject(BridgeProtocol.error("r2", "boom", "msg"))
        assertFalse(err.getBoolean("ok")); assertEquals("boom", err.getJSONObject("error").getString("code"))
    }

    @Test fun eventsHaveNameAndData() {
        val e = JSONObject(BridgeProtocol.event("location.sample", JSONObject().put("sequence", 1)))
        assertEquals("event", e.getString("type")); assertEquals("location.sample", e.getString("name"))
        assertEquals(1, e.getJSONObject("data").getInt("sequence"))
    }
}
