package io.github.sajadinmaker.vpnbox

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.github.sajadinmaker.vpnbox.data.CacheStore
import io.github.sajadinmaker.vpnbox.data.Server
import io.github.sajadinmaker.vpnbox.data.ServerCache
import io.github.sajadinmaker.vpnbox.data.SessionIntent
import io.github.sajadinmaker.vpnbox.data.SessionStore
import io.github.sajadinmaker.vpnbox.data.UserError
import io.github.sajadinmaker.vpnbox.data.VpnGate
import io.github.sajadinmaker.vpnbox.data.VpnGateParser
import io.github.sajadinmaker.vpnbox.data.backoffSeconds
import io.github.sajadinmaker.vpnbox.data.checkPingSettings
import io.github.sajadinmaker.vpnbox.data.selectServers
import io.github.sajadinmaker.vpnbox.data.validateArgs
import io.github.sajadinmaker.vpnbox.engine.EngineEvent
import io.github.sajadinmaker.vpnbox.engine.SimulatedEngine
import java.io.File
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class Screen { HOME, TERMINAL }

/** The chips row: connect → watch → kill → recovered (mirrors the reel beats). */
enum class WatchPhase { CONNECT, WATCH, KILL, RECOVERED, FAILED }

data class CountryPick(val cc: String, val country: String, val servers: Int)

data class HomeUi(
    val connected: Boolean = false,
    val servers: Int = 0,
    val countries: Int = 0,
    val cacheAgeMin: Long? = null,
    val geoLabel: String = "",
    val message: String = "",
)

data class TerminalLine(val text: String, val tone: Tone) {
    enum class Tone { PLAIN, OK, WARN, ERR, ACCENT }
}

data class TerminalUi(
    val phase: WatchPhase = WatchPhase.CONNECT,
    val lines: List<TerminalLine> = emptyList(),
    val cycle: Int = 0,
    val cycles: Int = 3,
)

class VpnViewModel(
    filesDir: File,
    private val engine: SimulatedEngine = SimulatedEngine(),
) : ViewModel() {

    private val cacheStore = CacheStore(File(filesDir, "servers.json"))
    private val sessionStore = SessionStore(File(filesDir, "session.json"))

    val screen = MutableStateFlow(Screen.HOME)
    val home = MutableStateFlow(HomeUi())
    val terminal = MutableStateFlow(TerminalUi())
    val countries = MutableStateFlow<List<CountryPick>>(emptyList())

    private var cache: ServerCache? = null
    private var intent: SessionIntent? = null
    private var connectJob: Job? = null
    private var watchJob: Job? = null
    private var hasHandshake = false
    private var liveKillSignal = false
    private val cycleMax = 3

    fun start() {
        viewModelScope.launch {
            engine.events.collect { consumeEngineEvent(it) }
        }
        cache = cacheStore.load()
        intent = sessionStore.load()
        projectCacheToHome()
        refreshGeoLabel()
    }

    private fun projectCacheToHome() {
        val servers = cache?.servers.orEmpty()
        home.update { h ->
            h.copy(
                connected = h.connected,
                servers = servers.size,
                countries = servers.map { it.cc }.distinct().size,
                cacheAgeMin = cache?.let {
                    (System.currentTimeMillis() - it.updated) / 60_000L
                },
            )
        }
    }

    private fun refreshGeoLabel() {
        viewModelScope.launch {
            val g = VpnGate.fetchGeo() ?: return@launch
            val where = listOf(g["city"], g["regionName"], g["country"])
                .filter { !it.isNullOrBlank() }.joinToString(", ")
            home.update {
                it.copy(geoLabel = "${g["query"]}  ·  $where")
            }
        }
    }

    // ---- refresh ------------------------------------------------------------

    fun refresh() {
        connectJob?.cancel()
        connectJob = viewModelScope.launch {
            home.update { it.copy(message = "refreshing the live server list …") }
            try {
                val text = VpnGate.fetchListText()
                val servers = VpnGateParser.parse(text)
                VpnGate.enrichCity(servers)
                val fresh = ServerCache(System.currentTimeMillis(), servers)
                cacheStore.save(fresh)
                cache = fresh
                projectCacheToHome()
                rebuildCountries()
                val responsive = servers.count { it.ping in 1L..<900L }
                home.update {
                    it.copy(message = "refreshed · ${servers.size} servers · " +
                        "${servers.map { s -> s.cc }.distinct().size} countries · " +
                        "$responsive responsive right now")
                }
            } catch (e: Exception) {
                home.update {
                    it.copy(message = "refresh failed — ${e.message ?: "offline?"}")
                }
            }
        }
    }

    fun rebuildCountries() {
        val servers = cache?.servers.orEmpty()
        countries.value = servers
            .groupBy { it.cc }
            .map { (cc, rows) -> CountryPick(cc, rows.first().country, rows.size) }
            .sortedWith(compareBy({ -it.servers }, { it.cc }))
    }

    // ---- connect ------------------------------------------------------------

    fun connect(country: String?, city: String?) {
        screen.value = Screen.TERMINAL
        terminal.value = TerminalUi(phase = WatchPhase.CONNECT)
        intent = null
        connectJob?.cancel()
        connectJob = viewModelScope.launch {
            try {
                val ping = 10
                val exit = checkPingSettings(ping, 60)
                validateArgs(skip = 0, index = null, maxTries = 3,
                             ping = ping, pingExit = exit)
                var c = cache ?: cacheStore.load()
                if (c == null ||
                    System.currentTimeMillis() - c.updated > 30 * 60_000L) {
                    if (c != null) {
                        line("server list missing or >30 min old — refreshing …",
                             TerminalLine.Tone.WARN)
                    }
                    val text = VpnGate.fetchListText()
                    val servers = VpnGateParser.parse(text)
                    VpnGate.enrichCity(servers)
                    c = ServerCache(System.currentTimeMillis(), servers)
                    cacheStore.save(c)
                    cache = c
                    rebuildCountries()
                }
                val servers0 = c?.servers ?: emptyList()
                if (servers0.isEmpty()) {
                    line("refresh completed but the list is unusable",
                         TerminalLine.Tone.ERR)
                    terminal.update { it.copy(phase = WatchPhase.FAILED) }
                    return@launch
                }
                val (sel, why) = selectServers(servers0, country, city)
                if (sel.isEmpty()) {
                    line("no candidates. ${why.ifBlank { "try another country" }}",
                         TerminalLine.Tone.ERR)
                    terminal.update { it.copy(phase = WatchPhase.FAILED) }
                    return@launch
                }
                for ((i, r) in sel.take(3).withIndex()) {
                    attemptLine(i, sel.size, r)
                    if (engine.start(r, keepalive = Pair(ping, exit)).isSuccess) {
                        succeed(r, country, city, exit)
                        startWatchLoop(country, city, exit)
                        return@launch
                    }
                }
                line("all attempts failed. volunteer servers are dynamic — " +
                     "try: refresh", TerminalLine.Tone.ERR)
                terminal.update { it.copy(phase = WatchPhase.FAILED) }
            } catch (e: UserError) {
                line("× ${e.message}", TerminalLine.Tone.ERR)
                terminal.update { it.copy(phase = WatchPhase.FAILED) }
            } catch (e: Exception) {
                line("× connect failed: ${e.message ?: "network error"}",
                     TerminalLine.Tone.ERR)
                terminal.update { it.copy(phase = WatchPhase.FAILED) }
            }
        }
    }

    private suspend fun attemptLine(i: Int, total: Int, r: Server) {
        val where = r.city.ifBlank { r.host }
        terminal.update {
            it.copy(lines = it.lines + TerminalLine(
                "attempt ${i + 1}/$total: ${r.country} / $where (${r.ip})  " +
                    "[${r.proto}/${r.port.ifBlank { "?" }} ping ${r.ping}ms]",
                TerminalLine.Tone.ACCENT))
        }
    }

    private suspend fun succeed(
        r: Server,
        country: String?,
        city: String?,
        exit: Int,
    ) {
        hasHandshake = true
        val fresh = SessionIntent(
            country = country ?: r.country, city = city,
            proto = r.proto, ping = 10, pingExit = exit,
        )
        intent = fresh
        sessionStore.save(fresh)
        home.update { it.copy(connected = true) }
        line("CONNECTED  via ${r.host}  [${r.country}" +
             (if (r.city.isNotBlank()) " → ${r.city}" else "") + "]",
             TerminalLine.Tone.OK)
        VpnGate.fetchGeo()?.let { geo ->
            val where = listOf(geo["city"], geo["regionName"], geo["country"])
                .filter { !it.isNullOrBlank() }.joinToString(", ")
            line("exit IP : ${geo["query"]}", TerminalLine.Tone.PLAIN)
            line("location: $where  (isp ${geo["isp"]?.ifBlank { "?" }})",
                 TerminalLine.Tone.PLAIN)
        }
        line("disconnect from Home → Disconnect", TerminalLine.Tone.PLAIN)
        terminal.update { it.copy(phase = WatchPhase.WATCH) }
        refreshGeoLabel()
    }

    private fun line(text: String, tone: TerminalLine.Tone) {
        terminal.update { it.copy(lines = it.lines + TerminalLine(text, tone)) }
    }

    // ---- watch --------------------------------------------------------------

    private fun startWatchLoop(country: String?, city: String?, exit: Int) {
        watchJob?.cancel()
        watchJob = viewModelScope.launch {
            var failures = 0
            while (true) {
                delay(1500)
                if (!liveKillSignal) {
                    if (sessionStore.load()?.stopped == true) {
                        return@launch          // disconnect while we were watching
                    }
                    continue                   // the simulated daemon never dies on its own
                }
                liveKillSignal = false
                line("tunnel killed — daemon terminated", TerminalLine.Tone.WARN)
                terminal.update { it.copy(phase = WatchPhase.KILL) }
                val pending = intent ?: return@launch
                if (pending.stopped) {        // user disconnect beat the watchdog
                    line("[watch] user disconnected — honoring it",
                         TerminalLine.Tone.PLAIN)
                    hasHandshake = false
                    home.update { it.copy(connected = false) }
                    return@launch
                }
                line("[watch] tunnel down for 4 s — reconnecting " +
                     "(cycle ${failures + 1}/$cycleMax) …", TerminalLine.Tone.WARN)
                val (sel, _) = selectServers(cache?.servers.orEmpty(), country, city)
                var recovered: Server? = null
                for (r in sel.take(3)) {
                    attemptLine(0, 3, r)
                    if (engine.start(r, keepalive = Pair(10, exit)).isSuccess) {
                        recovered = r
                        break
                    }
                }
                val rec = recovered
                if (rec == null) {
                    failures++
                    if (failures >= cycleMax) {
                        line("[watch] $failures recovery cycles failed — giving " +
                             "up. The tunnel is down; try: refresh",
                             TerminalLine.Tone.ERR)
                        terminal.update { it.copy(phase = WatchPhase.FAILED) }
                        hasHandshake = false
                        home.update { it.copy(connected = false) }
                        return@launch
                    }
                    val wait = backoffSeconds(failures)
                    line("[watch] recovery $failures/$cycleMax failed — " +
                         "retrying in $wait s", TerminalLine.Tone.ERR)
                    val until = System.currentTimeMillis() + wait * 1000
                    while (System.currentTimeMillis() < until) {
                        delay(1000)
                        if (sessionStore.load()?.stopped == true) return@launch
                    }
                } else {
                    // reviving a session needs a non-null intent; the guard
                    // above (`pending = intent ?: return@launch`) guarantees it
                    val saved = intent
                    if (saved == null) return@launch
                    val revived = saved.copy(stopped = false)
                    intent = revived
                    sessionStore.save(revived)
                    home.update { it.copy(connected = true) }
                    line("[watch] recovered the tunnel (via ${rec.host}) " +
                         "after 4 s of downtime", TerminalLine.Tone.OK)
                    terminal.update { it.copy(phase = WatchPhase.RECOVERED) }
                    failures = 0
                }
            }
        }
    }

    /** "Kill tunnel" chip — the same one-shot the real engine's Down event
     * will carry once the OpenVPN core lands. */
    fun killTunnel() {
        liveKillSignal = true
    }

    fun dismissAndGoHome() {
        screen.value = Screen.HOME
    }

    private fun consumeEngineEvent(e: EngineEvent) {
        when (e) {
            is EngineEvent.Log -> {
                val tone = when {
                    e.line.startsWith("×") -> TerminalLine.Tone.ERR
                    VpnGate.OK_MARKER in e.line -> TerminalLine.Tone.OK
                    else -> TerminalLine.Tone.PLAIN
                }
                terminal.update {
                    it.copy(lines = it.lines + TerminalLine(e.line, tone))
                }
                if (tone == TerminalLine.Tone.ERR) {
                    terminal.update { it.copy(phase = WatchPhase.KILL) }
                }
            }
            is EngineEvent.HandshakeFailed -> {
                for (l in e.excerpt) line("× $l", TerminalLine.Tone.ERR)
            }
            EngineEvent.HandshakeOk -> Unit  // succeed() renders the OK block
            EngineEvent.Down -> Unit         // watchdog consumes its own signal
        }
    }

    // ---- disconnect ---------------------------------------------------------

    fun disconnect() {
        watchJob?.cancel()
        connectJob?.cancel()
        engine.stop()
        hasHandshake = false
        // intent first: the teardown must never race the watchdog into
        // resurrecting the tunnel the user just asked to stop
        val saved = intent
        if (saved != null) {
            sessionStore.stop(saved)
            intent = saved.copy(stopped = true, stoppedAt = System.currentTimeMillis())
        }
        home.update {
            it.copy(
                connected = false,
                message = "disconnected — you are back on your connection",
            )
        }
        screen.value = Screen.HOME
        rebuildCountries()
    }
}
