package net.linspad.atlasphone.running.auth

data class ParsedPairing(val baseUrl: String?, val code: String)

/**
 * Parses the QR/text payload built by the web page (03_Application/RunningTracker/src/pairingPayload.ts):
 * "ATLASRUN1|<base_url>|<code>" or a bare code. The prefix literal is repeated in backend/config.py and in
 * pairingPayload.ts (three-place literal; each parser has a test). The code is normalised (trimmed, upper case).
 */
object PairingPayload {
    const val PREFIX = "ATLASRUN1"
    // Same alphabet as the backend (no 0 O 1 I L), 8 characters.
    private val CODE = Regex("^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{8}$")

    fun parse(raw: String): ParsedPairing? {
        val text = raw.trim()
        if (text.startsWith("$PREFIX|")) {
            val parts = text.split('|')
            if (parts.size != 3) return null
            val url = parts[1].trim()
            val code = parts[2].trim().uppercase()
            if (!url.startsWith("https://") || url.length <= "https://".length || !CODE.matches(code)) return null
            return ParsedPairing(url.trimEnd('/'), code)
        }
        val code = text.uppercase()
        return if (CODE.matches(code)) ParsedPairing(null, code) else null
    }
}
