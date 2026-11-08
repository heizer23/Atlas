package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.HttpResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class GhostClientTest {
    private val base = "https://atlas.example.ts.net:8443"
    private val route = "22222222-2222-2222-2222-222222222222"
    private val ghost = "11111111-1111-1111-1111-111111111111"

    @Test fun preparedRunCarriesRouteAndGhostIds_andOldServersStillParse() {
        val t = FakeTransport { r ->
            if (r.url.endsWith("/prepared-runs"))
                HttpResponse(200, """{"prepared_runs":[
                    {"id":"p1","short_id":"ABC234","run_type":"continuous","title":"Race","planned_for":null,"expires_at":"2030-01-01T00:00:00Z","route_id":"$route","ghost_run_id":"$ghost"},
                    {"id":"p2","short_id":"ABC235","run_type":"continuous","title":null,"planned_for":null,"expires_at":"2030-01-01T00:00:00Z","route_id":null,"ghost_run_id":null},
                    {"id":"p3","short_id":"ABC236","run_type":"continuous","title":null,"planned_for":null,"expires_at":"2030-01-01T00:00:00Z"}]}""")
            else HttpResponse(404, "{}")
        }
        val runs = (AtlasClient(base, { "tok" }, t).preparedRuns() as AtlasResult.Success).value
        assertEquals(route, runs[0].routeId); assertEquals(ghost, runs[0].ghostRunId)
        assertNull(runs[1].routeId); assertNull(runs[1].ghostRunId); assertNull(runs[2].ghostRunId)
    }

    @Test fun routeAndProfileAreDownloadedWithBearerAndParsed() {
        val t = FakeTransport { r ->
            when {
                r.url.endsWith("/native/routes/$route") -> HttpResponse(200, """{"route_id":"$route","name":"Stadtpark Small","geometry_version":1,"reference_distance_m":4216.78,"is_loop":true,"geometry":[[53.59,10.0,0.0],[53.6,10.0,1111.9]]}""")
                r.url.endsWith("/native/runs/$ghost/ghost-profile") -> HttpResponse(200, """{"run_id":"$ghost","route_id":"$route","geometry_version":1,"algo_version":1,"time_basis":"moving_seconds","end_progress_m":4216.78,"duration_s":1936.0,"points":[[0.0,0.0,92.0],[1.0,3.5,null],[1936.0,4216.78,162.0]]}""")
                else -> HttpResponse(404, "{}")
            }
        }
        val c = AtlasClient(base, { "tok" }, t)
        val rt = (c.route(route) as AtlasResult.Success).value
        assertEquals("Stadtpark Small", rt.name); assertTrue(rt.isLoop); assertEquals(2, rt.points.size)
        val p = (c.ghostProfile(ghost) as AtlasResult.Success).value
        assertEquals(3, p.points.size); assertNull(p.points[1].hr); assertEquals(162.0, p.points[2].hr!!, 0.0)
        assertTrue(t.requests.all { it.headers["Authorization"] == "Bearer tok" })
        assertTrue(c.ghostProfile("not-there").let { it is AtlasResult.NotFound })
    }
}
