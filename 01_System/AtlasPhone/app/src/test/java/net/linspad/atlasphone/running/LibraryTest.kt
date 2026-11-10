package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.ghost.Library
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.OffsetDateTime

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LibraryTest {
    private val server = """{"routes":[{"route_id":"r1","name":"Stadtpark","geometry_version":1,"reference_distance_m":4010.5}],
        "runs":[{"run_id":"a","route_id":"r1","started_at":"2026-11-08T09:00:00+00:00","moving_s":1500.0,"distance_m":4020.0,"category":"4 km · HR 140","avg_hr":141.2,"geometry_version":1,"algo_version":1},
                {"run_id":"b","route_id":"r1","started_at":"2026-11-01T09:00:00Z","moving_s":null,"distance_m":null,"category":null,"avg_hr":null,"geometry_version":1,"algo_version":1}]}"""

    @Test fun parsesServerShapeAndSurvivesTheCache() {
        val lib = Library.fromJson(JSONObject(server)) { OffsetDateTime.parse(it.getString("started_at")).toInstant().toEpochMilli() }
        assertEquals(2, lib.runsOn("r1").size)
        assertEquals("4 km · HR 140", lib.runs[0].category)
        assertNull(lib.runs[1].movingS)
        val again = Library.fromCacheJson(lib.toJson())
        assertEquals(lib, again)
    }
}
