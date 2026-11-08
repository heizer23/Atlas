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
) {
    fun toJson(): String = JSONObject()
        .put("run_id", runId).put("route_id", routeId).put("geometry_version", geometryVersion)
        .put("points", JSONArray(points.map { JSONArray(listOf(it.t, it.s, it.hr ?: JSONObject.NULL)) }))
        .toString()

    companion object {
        fun fromJson(o: JSONObject): GhostProfile {
            val a = o.getJSONArray("points")
            val pts = (0 until a.length()).map { i ->
                a.getJSONArray(i).let { GhostPoint(it.getDouble(0), it.getDouble(1), if (it.isNull(2)) null else it.getDouble(2)) }
            }
            require(pts.size >= 2) { "ghost profile needs at least two points" }
            return GhostProfile(o.getString("run_id"), o.getString("route_id"), o.getInt("geometry_version"), pts)
        }
        fun fromJson(json: String) = fromJson(JSONObject(json))
    }
}
