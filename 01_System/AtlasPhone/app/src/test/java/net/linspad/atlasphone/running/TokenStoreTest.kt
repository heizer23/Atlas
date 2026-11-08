package net.linspad.atlasphone.running

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import net.linspad.atlasphone.running.auth.SecretCipher
import net.linspad.atlasphone.running.auth.TokenStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Reversible but unreadable stand-in for the Keystore cipher (the real one needs an Android device). */
private class FakeCipher : SecretCipher {
    override fun encrypt(plain: ByteArray) = byteArrayOf(0x7f) + plain.reversedArray().map { (it.toInt() xor 0x5a).toByte() }.toByteArray()
    override fun decrypt(blob: ByteArray): ByteArray {
        require(blob.isNotEmpty() && blob[0] == 0x7f.toByte()) { "tampered" }
        return blob.drop(1).map { (it.toInt() xor 0x5a).toByte() }.toByteArray().reversedArray()
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class TokenStoreTest {
    private lateinit var context: Context
    private val secret = "tok-SECRET-0123456789abcdefghijklmnopqrstuvwxyz"

    @Before fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("test_pairing", Context.MODE_PRIVATE).edit().clear().commit()
    }

    private fun store() = TokenStore(context.getSharedPreferences("test_pairing", Context.MODE_PRIVATE), FakeCipher())

    @Test fun pairingIsSavedReadAndCleared() {
        val s = store()
        assertNull(s.token()); assertFalse(s.isPaired())
        s.savePairing("https://atlas.example.ts.net:8443/", "dev-1", secret)
        assertEquals(secret, s.token())
        assertEquals("https://atlas.example.ts.net:8443", s.baseUrl())
        assertTrue(s.isPaired())
        assertEquals(secret, store().token()) // a new instance reads the persisted value
        s.clear()
        assertNull(s.token()); assertFalse(s.isPaired())
        assertEquals("https://atlas.example.ts.net:8443", s.baseUrl()) // URL kept for the re-pair form
    }

    @Test fun preferencesNeverHoldThePlaintextToken() {
        store().savePairing("https://atlas.example.ts.net:8443", "dev-1", secret)
        val all = context.getSharedPreferences("test_pairing", Context.MODE_PRIVATE).all
        assertNotNull(all["token_blob"])
        assertTrue(all.values.none { it.toString().contains(secret) })
        assertTrue(all.values.none { it.toString().contains(secret.reversed()) })
    }

    @Test fun corruptBlobReadsAsNoToken() {
        context.getSharedPreferences("test_pairing", Context.MODE_PRIVATE).edit().putString("token_blob", "AAAA").commit()
        assertNull(store().token())
        context.getSharedPreferences("test_pairing", Context.MODE_PRIVATE).edit().putString("token_blob", "###not-base64###").commit()
        assertNull(store().token())
    }

    @Test fun nonHttpsBaseUrlIsRefused() {
        val e = assertThrows(IllegalArgumentException::class.java) { store().savePairing("http://atlas.example:8443", "dev-1", secret) }
        assertFalse(e.message!!.contains(secret))
        assertNull(store().token())
    }
}
