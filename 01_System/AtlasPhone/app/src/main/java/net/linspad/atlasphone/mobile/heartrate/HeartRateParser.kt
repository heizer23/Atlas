package net.linspad.atlasphone.mobile.heartrate

/** Result of parsing a Heart Rate Measurement (0x2A37) notification. */
data class ParsedHeartRate(
    val bpm: Int,
    /** RR intervals in milliseconds (1/1024 s resolution converted), null when the sensor sent none. */
    val rrIntervalsMs: List<Int>?,
    /** null = sensor does not report contact. */
    val sensorContact: Boolean?,
)

/** Parser for the standard Bluetooth Heart Rate Measurement characteristic. Pure, no Android dependencies. */
object HeartRateParser {
    fun parse(data: ByteArray?): ParsedHeartRate? {
        if (data == null || data.size < 2) return null
        val flags = data[0].toInt() and 0xff
        val sixteenBit = flags and 0x01 != 0
        val contactBits = (flags shr 1) and 0x03
        val energyPresent = flags and 0x08 != 0
        val rrPresent = flags and 0x10 != 0

        var i = 1
        val bpm: Int
        if (sixteenBit) {
            if (data.size < 3) return null
            bpm = u8(data, i) or (u8(data, i + 1) shl 8)
            i += 2
        } else {
            bpm = u8(data, i)
            i += 1
        }
        if (energyPresent) i += 2

        val rr = ArrayList<Int>()
        if (rrPresent) {
            while (i + 1 < data.size) {
                val raw = u8(data, i) or (u8(data, i + 1) shl 8)
                rr.add(Math.round(raw * 1000.0 / 1024.0).toInt())
                i += 2
            }
        }
        // Contact: 0/1 = not supported, 2 = supported but not detected, 3 = detected.
        val contact = if (contactBits < 2) null else contactBits == 3
        return ParsedHeartRate(bpm, rr.takeIf { it.isNotEmpty() }, contact)
    }

    private fun u8(b: ByteArray, i: Int) = b[i].toInt() and 0xff
}
