package net.linspad.atlasphone.running.ghost

import java.io.File
import java.util.UUID

/**
 * Offline copy of the downloaded route and ghost profile (JSON files). Lives in the no-backup directory: it is derived,
 * re-downloadable data. Ids are validated as UUIDs so they can never form a path outside [dir].
 */
class GhostCache(private val dir: File) {
    private fun file(kind: String, id: String): File {
        val uuid = UUID.fromString(id).toString()
        return File(dir, "$kind-$uuid.json")
    }

    fun saveRoute(route: RouteGeometry) = write(file("route", route.routeId), route.toJson())
    fun saveProfile(profile: GhostProfile) = write(file("ghost", profile.runId), profile.toJson())

    fun route(routeId: String): RouteGeometry? = read(file("route", routeId))?.let { runCatching { RouteGeometry.fromJson(it) }.getOrNull() }
    fun profile(runId: String): GhostProfile? = read(file("ghost", runId))?.let { runCatching { GhostProfile.fromJson(it) }.getOrNull() }

    /** True when the race can run offline: both the route and the ghost profile (for that route) are stored and readable. */
    fun isReady(routeId: String, ghostRunId: String): Boolean {
        val r = route(routeId) ?: return false
        val p = profile(ghostRunId) ?: return false
        return p.routeId == r.routeId && p.geometryVersion == r.geometryVersion
    }

    private fun write(f: File, text: String) {
        dir.mkdirs()
        val tmp = File(dir, f.name + ".tmp")
        tmp.writeText(text)
        if (!tmp.renameTo(f)) { f.writeText(text); tmp.delete() }
    }

    private fun read(f: File): String? = if (f.isFile) runCatching { f.readText() }.getOrNull() else null
}
