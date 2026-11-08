package net.linspad.atlasphone.running.auth

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Encrypts small secrets. Implementations must never log their input. */
interface SecretCipher {
    /** Returns iv + ciphertext. */
    fun encrypt(plain: ByteArray): ByteArray
    /** Inverse of [encrypt]; throws on tampering or a missing key. */
    fun decrypt(blob: ByteArray): ByteArray
}

/** AES/GCM/NoPadding with a non-exportable key generated in the AndroidKeyStore on first use. */
class KeystoreAesGcmCipher(private val alias: String = "atlasphone_run_token") : SecretCipher {
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        val spec = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply { init(spec) }.generateKey()
    }

    override fun encrypt(plain: ByteArray): ByteArray {
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        return c.iv + c.doFinal(plain)
    }

    override fun decrypt(blob: ByteArray): ByteArray {
        require(blob.size > IV_BYTES) { "blob too short" }
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, blob, 0, IV_BYTES))
        }
        return c.doFinal(blob, IV_BYTES, blob.size - IV_BYTES)
    }

    private companion object { const val IV_BYTES = 12 }
}

/**
 * Device token and server URL. The token is stored only as Keystore-encrypted ciphertext in the prefs file
 * `atlas_run_pairing` (excluded from backup). It is never logged and never put into URLs or deep links.
 */
class TokenStore(private val prefs: SharedPreferences, private val cipher: SecretCipher) {
    /** Rejects a non-https [baseUrl] (no cleartext, ever). */
    fun savePairing(baseUrl: String, deviceId: String, token: String) {
        require(baseUrl.startsWith("https://")) { "Atlas base URL must use https" }
        val blob = Base64.encodeToString(cipher.encrypt(token.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        prefs.edit().putString(KEY_URL, baseUrl.trimEnd('/')).putString(KEY_DEVICE, deviceId).putString(KEY_BLOB, blob).apply()
    }

    /** Decrypted token, or null when absent or when decryption fails (corrupt blob, lost key). */
    fun token(): String? {
        val blob = prefs.getString(KEY_BLOB, null) ?: return null
        return try {
            String(cipher.decrypt(Base64.decode(blob, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (e: Exception) {
            null
        }
    }

    fun baseUrl(): String? = prefs.getString(KEY_URL, null)

    fun isPaired(): Boolean = token() != null && baseUrl() != null

    /** Forget the pairing but keep the server URL for the re-pair form. */
    fun clear() {
        prefs.edit().remove(KEY_BLOB).remove(KEY_DEVICE).apply()
    }

    companion object {
        const val PREFS_NAME = "atlas_run_pairing"
        private const val KEY_URL = "base_url"
        private const val KEY_DEVICE = "device_id"
        private const val KEY_BLOB = "token_blob"

        fun create(context: Context) = TokenStore(
            context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE), KeystoreAesGcmCipher(),
        )
    }
}
