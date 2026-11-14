package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.hr.HrSmoothingMode
import net.linspad.atlasphone.running.metrics.SplitInfo
import net.linspad.atlasphone.running.recap.FinishStanding
import net.linspad.atlasphone.running.recap.RecapData
import net.linspad.atlasphone.running.recap.RecoverySummary
import net.linspad.atlasphone.running.settings.RunSettings
import net.linspad.atlasphone.running.settings.SettingsStore
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RunMetaCompatTest {
    /** A run meta as written by the previous build: none of the Sprint02 keys. */
    private val oldJson = """{"captureId":"old","state":"PENDING_UPLOAD","preparedShortId":null,"title":"Easy","startedAtMillis":1700000000000,
        "finishedAtMillis":1700001800000,"pauses":[],"summary":{"elapsedS":1800.0,"movingS":1800.0,"distanceM":5000.0,"avgPaceSPerKm":360.0,"avgHr":150.0},
        "uploadCursor":3,"lastError":null,"needsRepair":false,"routeId":null,"ghostRunId":null,"targetHr":null,"category":null}"""

    @Test fun oldMetaDecodesWithTheNewValuesAbsent() {
        val m = RunMeta.fromJson(oldJson)
        assertNull(m.runFinishedAtMillis); assertNull(m.recovery); assertNull(m.recap)
        assertEquals(RunState.PENDING_UPLOAD, m.state)
        assertEquals(5000.0, m.summary!!.distanceM, 0.0)
        // re-encode and decode again: still fine, still absent
        val again = RunMeta.fromJson(m.toJson())
        assertEquals(m, again)
        assertNull(JSONObject(m.toJson()).opt("runFinishedAtMillis")?.takeIf { it != JSONObject.NULL })
    }

    @Test fun newKeysRoundTripUnchanged() {
        val standing = FinishStanding(2, 3, 2, true, 110.5, true, 9.5, 120.0, false, 3, true)
        val recap = RecapData(standing, listOf(SplitInfo(1, 1000.0, 330.0, 330.0, 151.0, false), SplitInfo(2, 640.0, 220.0, 343.75, null, true)), 172,
            listOf(HrPoint(1_700_000_001_000, 150), HrPoint(1_700_000_002_000, 151)))
        val meta = RunMeta("new", RunState.RECOVERY, null, null, 1_700_000_000_000, null, emptyList(),
            RunSummary(300.0, 300.0, 1200.0, 250.0, 150.0), 0, null, false, null, null, null, null,
            runFinishedAtMillis = 1_700_000_300_000, recovery = RecoverySummary(172.0, 150.0, null, 22.0, null), recap = recap)
        assertEquals(meta, RunMeta.fromJson(meta.toJson()))
        val noStanding = meta.copy(state = RunState.PENDING_UPLOAD, recap = recap.copy(standing = null), recovery = null)
        assertEquals(noStanding, RunMeta.fromJson(noStanding.toJson()))
    }

    private class MapStore : SettingsStore {
        val map = HashMap<String, String>()
        override fun getString(key: String) = map[key]
        override fun putString(key: String, value: String) { map[key] = value }
    }

    @Test fun smoothingSettingDefaultsToFiveSecondsWhenUnsetOrUnknown() {
        val store = MapStore()
        val settings = RunSettings(store)
        assertEquals(HrSmoothingMode.ROLLING_5S, settings.hrSmoothing())
        store.map[RunSettings.KEY_HR_SMOOTHING] = "garbage"
        assertEquals(HrSmoothingMode.ROLLING_5S, settings.hrSmoothing())
        settings.setHrSmoothing(HrSmoothingMode.ROLLING_10S)
        assertEquals(HrSmoothingMode.ROLLING_10S, RunSettings(store).hrSmoothing())
        settings.setHrSmoothing(HrSmoothingMode.RAW)
        assertEquals(HrSmoothingMode.RAW, settings.hrSmoothing())
    }
}
