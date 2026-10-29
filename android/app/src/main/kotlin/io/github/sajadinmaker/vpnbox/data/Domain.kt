package io.github.sajadinmaker.vpnbox.data

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** User-input mistakes surface as readable dialogs, never stack traces. */
class UserError(msg: String) : RuntimeException(msg)

/** Sorting key — identical order to rank() in the CLI: valid pings first,
 * UDP preferred, then throughput, then ping, then VPN-Gate score. */
    val rankKey: Comparator<Server> = compareBy(
    { r: Server -> if (r.ping in 1L..<900L) 0 else 1 },
    { r: Server -> if (r.proto == "udp") 0 else 1 },
    { r: Server -> -r.speed },
    { r: Server -> if (r.ping > 0) r.ping else Long.MAX_VALUE },
    { r: Server -> -r.score },
)

/** Country/city narrowing — semantic twin of select_servers(). */
fun selectServers(
    servers: List<Server>,
    country: String? = null,
    city: String? = null,
): Pair<List<Server>, String> {
    var out = servers
    val why = StringBuilder()
    if (!country.isNullOrBlank()) {
        val q = country.trim()
        val exact = out.filter { it.cc == q.uppercase() }
        out = if (exact.isEmpty()) {
            val named = servers.filter { q.lowercase() in it.country.lowercase() }
            if (named.isEmpty()) {
                return Pair(emptyList(), "No servers found for '$q'. Refresh the list and try again.")
            }
            named
        } else {
            exact
        }
    }
    if (!city.isNullOrBlank()) {
        val tmp = out.filter {
            city.lowercase() in "${it.city} ${it.isp} ${it.host}".lowercase()
        }
        if (tmp.isEmpty()) {
            // No match: return nothing and say why. (The Python CLI leaves
            // the unfiltered list here — the --city filter then silently
            // connects anyway. The app refuses to ignore a missed filter.)
            val cities = out.mapNotNull { it.city.takeIf(String::isNotBlank) }.distinct().sorted()
            val avail = cities.take(12).joinToString(", ").ifBlank {
                "(no city data available)"
            }
            why.append("No servers in $country match city '$city'. Available cities: $avail")
            out = emptyList()
        } else {
            out = tmp
        }
    }
    return Pair(out.sortedWith(rankKey), why.toString())
}

/** Reject values that would silently select zero servers or emit an
 * invalid tunnel profile — twin of validate_connect_args(). */
fun validateArgs(
    skip: Int,
    index: Int?,
    maxTries: Int,
    ping: Int,
    pingExit: Int,
) {
    if (skip < 0) throw UserError("Skip must be 0 or greater")
    if (index != null && index < 1) throw UserError("Index must be 1 or greater")
    if (maxTries < 1) throw UserError("Retry count must be 1 or greater")
    checkPingSettings(ping, pingExit)
}

/** Twin of check_ping_settings(): 0/0 is legal (probe off), nonsense is not. */
fun checkPingSettings(ping: Int, pingExit: Int): Int {
    var exitAfter = pingExit
    if (ping < 0) throw UserError("Ping interval must be 0 or greater")
    if (pingExit < 0) throw UserError("Ping exit must be 0 or greater")
    if (ping == 0) exitAfter = 0                  // probe off ⇒ exit 0 (redundant)
    if (ping > 0 && exitAfter in 1..ping) throw UserError(
        "Ping exit ($exitAfter) must be greater than the ping interval ($ping), or 0 to disable")
    return exitAfter
}

/** Twin of backoff_seconds(): 30 s doubling with a 300 s cap. */
fun backoffSeconds(fail: Int, base: Long = 30, cap: Long = 300): Long {
    return minOf(cap, base * (1L shl (fail - 1).coerceAtMost(62)))
}

/** Tunnel profile builder — twin of build_conf() in the CLI. Never emits
 * `ping 0` (the probe is off entirely instead). */
fun buildConf(
    r: Server,
    keepalive: Pair<Int, Int>? = Pair(VpnGate.PING_DEFAULT, VpnGate.PING_EXIT_DEFAULT),
    generated: String = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
        .format(Date()),
): String {
    val lines = r.cfg.lineSequence().filter { l ->
        val t = l.trim()
        t.isNotEmpty() && !t.lowercase().startsWithAny(VpnGate.STRIP_PREFIXES)
    }.joinToString("\n")
    val sb = StringBuilder(VpnGate.EXTRA_CONFIG)
    if (keepalive != null) {
        val (interval, exitAfter) = keepalive
        if (interval > 0 && exitAfter > 0) {
            // OpenVPN 3 form: `keepalive <interval> <timeout>` probe both ways.
            // The v2 `ping`/`ping-exit` pair is fatal for the OpenVPN3 core
            // ("Option allowed only to be pushed by the server"); the keepalive
            // timeout still ends a dead tunnel, and the watchdog re-connects.
            sb.append("\nkeepalive ").append(interval)
                .append(' ').append(exitAfter).append('\n')
        }
    }
    val header = "### vpnbox profile — server ${r.host} (${r.country})\n" +
        "### ip=${r.ip} city=${r.city.ifBlank { "?" }} isp=${r.isp.ifBlank { "?" }}\n" +
        "### generated $generated\n"
    return header + lines + "\n" + sb
}

private fun String.startsWithAny(prefixes: List<String>) = prefixes.any { startsWith(it) }

/** Saved session — twin of the CLI's session.json: an intent while up,
 * a `stopped` tombstone after a disconnect, so a watchdog can tell the
 * difference between "daemon died" and "user quit". */
@Serializable
data class SessionIntent(
    val country: String? = null,
    val city: String? = null,
    val proto: String? = null,
    val ping: Int = VpnGate.PING_DEFAULT,
    val pingExit: Int = VpnGate.PING_EXIT_DEFAULT,
    val recovery: Boolean = false,
    val stopped: Boolean = false,
    val stoppedAt: Long = 0,
)

class SessionStore(private val file: File) {
    private val json = Json { ignoreUnknownKeys = true }

    fun save(intent: SessionIntent) = atomicWrite(file, json.encodeToString(intent))

    /** Loading honors the tombstone: a stopped session still loads (so the
     * watchdog can see it), but `stoppedAt` marks the disconnect. */
    fun load(): SessionIntent? {
        return try {
            json.decodeFromString<SessionIntent>(file.readText())
        } catch (e: Exception) {
            null                                          // garbage file = no session
        }
    }

    /** Disconnect: keep the intent, mark it stopped — a slow teardown must
     * never race the watchdog into resurrecting the tunnel (CLI clear_session). */
    fun stop(intent: SessionIntent) =
        save(intent.copy(stopped = true, stoppedAt = System.currentTimeMillis()))

    fun clear() = file.delete()
}

/** Crash-safe store file writes: temp file + rename (copy-to fallback).
 * App-private `filesDir` already enforces private mode on Android. */
fun atomicWrite(target: File, text: String) {
    val tmp = File(target.parentFile, target.name + ".tmp")
    tmp.writeText(text)
    if (!tmp.renameTo(target)) {
        target.delete()
        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
    }
}

/** Cache holder for the parsed server list with its update timestamp. */
class CacheStore(private val file: File) {
    private val json = Json { ignoreUnknownKeys = true }

    fun save(cache: ServerCache) = atomicWrite(file, json.encodeToString(cache))

    fun load(): ServerCache? {
        return try {
            json.decodeFromString<ServerCache>(file.readText())
        } catch (e: Exception) {
            null                                          // malformed cache is ignored
        }
    }
}
