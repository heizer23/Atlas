package net.linspad.atlasphone.running.ghost

import org.json.JSONArray
import org.json.JSONObject

/** One vertex of the reference route: position and cumulative distance along the (simplified) path. */
data class RoutePoint(val lat: Double, val lon: Double, val cumM: Double)

/** Immutable reference route as served by `GET /native/routes/{id}`. Progress is measured along this path. */
data class RouteGeometry(
    val routeId: String,
    val name: String,
    val geometryVersion: Int,
    val referenceDistanceM: Double,
    val isLoop: Boolean,
    val points: List<RoutePoint>,
) {
    fun toJson(): String = JSONObject()
        .put("route_id", routeId).put("name", name).put("geometry_version", geometryVersion)
        .put("reference_distance_m", referenceDistanceM).put("is_loop", isLoop)
        .put("geometry", JSONArray(points.map { JSONArray(listOf(it.lat, it.lon, it.cumM)) }))
        .toString()

    companion object {
        fun fromJson(o: JSONObject): RouteGeometry {
            val g = o.getJSONArray("geometry")
            val pts = (0 until g.length()).map { i -> g.getJSONArray(i).let { RoutePoint(it.getDouble(0), it.getDouble(1), it.getDouble(2)) } }
            require(pts.size >= 2) { "route needs at least two points" }
            return RouteGeometry(
                o.getString("route_id"), o.getString("name"), o.getInt("geometry_version"),
                o.getDouble("reference_distance_m"), o.getBoolean("is_loop"), pts,
            )
        }
        fun fromJson(json: String) = fromJson(JSONObject(json))
    }
}

/** [t] = moving seconds (pauses removed), [s] = progress along the route in metres, [hr] = recorded bpm or null (never filled). */
data class GhostPoint(val t: Double, val s: Double, val hr: Double?)

/** Ghost profile as served by `GET /native/runs/{id}/ghost-profile`. Usable without any server access. */
data class GhostProfile(
    val runId: String,
    val routeId: String,
    val geometryVersion: Int,
    val points: List<GhostPoint>,
    /** Server derivation version of the profile (2 = idle start trimmed); a cached profile of another version is re-downloaded. */
    val algoVersion: Int = 1,
) {
    fun toJson(): String = JSONObject()
        .put("run_id", runId).put("route_id", routeId).put("geometry_version", geometryVersion).put("algo_version", algoVersion)
        .put("points", JSONArray(points.map { JSONArray(listOf(it.t, it.s, it.hr ?: JSONObject.NULL)) }))
        .toString()

    companion object {
        fun fromJson(o: JSONObject): GhostProfile {
            val a = o.getJSONArray("points")
            val pts = (0 until a.length()).map { i ->
                a.getJSONArray(i).let { GhostPoint(it.getDouble(0), it.getDouble(1), if (it.isNull(2)) null else it.getDouble(2)) }
            }
            require(pts.size >= 2) { "ghost profile needs at least two points" }
            return GhostProfile(o.getString("run_id"), o.getString("route_id"), o.getInt("geometry_version"), pts, o.optInt("algo_version", 1))
        }
        fun fromJson(json: String) = fromJson(JSONObject(json))
    }
}

/** A route in the phone's library (geometry is fetched separately by id). */
data class LibraryRoute(val routeId: String, val name: String, val geometryVersion: Int, val referenceDistanceM: Double)

/** A completed run that can be a ghost on [routeId]: everything the picker shows, no samples. */
data class LibraryRun(
    val runId: String, val routeId: String, val startedAtMillis: Long, val movingS: Double?, val distanceM: Double?,
    val category: String?, val avgHr: Double?, val geometryVersion: Int, val algoVersion: Int = 1,
)

/** All routes and all qualified runs per route, as served by `GET /native/library` and cached for offline selection. */
data class Library(val routes: List<LibraryRoute>, val runs: List<LibraryRun>) {
    fun runsOn(routeId: String) = runs.filter { it.routeId == routeId }

    fun toJson(): String = JSONObject()
        .put("routes", JSONArray(routes.map { JSONObject().put("route_id", it.routeId).put("name", it.name)
            .put("geometry_version", it.geometryVersion).put("reference_distance_m", it.referenceDistanceM) }))
        .put("runs", JSONArray(runs.map { JSONObject().put("run_id", it.runId).put("route_id", it.routeId)
            .put("started_at_millis", it.startedAtMillis).put("moving_s", it.movingS ?: JSONObject.NULL)
            .put("distance_m", it.distanceM ?: JSONObject.NULL).put("category", it.category ?: JSONObject.NULL)
            .put("avg_hr", it.avgHr ?: JSONObject.NULL).put("geometry_version", it.geometryVersion).put("algo_version", it.algoVersion) }))
        .toString()

    companion object {
        val EMPTY = Library(emptyList(), emptyList())
        private fun JSONObject.d(k: String): Double? = if (isNull(k)) null else getDouble(k)

        /** [startedAt] converts the server's ISO text; the cache stores millis instead (see [toJson]). */
        fun fromJson(o: JSONObject, startedAt: (JSONObject) -> Long): Library {
            val r = o.getJSONArray("routes"); val u = o.getJSONArray("runs")
            return Library(
                (0 until r.length()).map { r.getJSONObject(it).let { x -> LibraryRoute(x.getString("route_id"), x.getString("name"), x.getInt("geometry_version"), x.getDouble("reference_distance_m")) } },
                (0 until u.length()).map { u.getJSONObject(it).let { x ->
                    LibraryRun(x.getString("run_id"), x.getString("route_id"), startedAt(x), x.d("moving_s"), x.d("distance_m"),
                        if (x.isNull("category")) null else x.getString("category"), x.d("avg_hr"), x.getInt("geometry_version"), x.optInt("algo_version", 1))
                } },
            )
        }
        fun fromCacheJson(json: String): Library = fromJson(JSONObject(json)) { it.getLong("started_at_millis") }
    }
}
