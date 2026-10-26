package io.github.sajadinmaker.vpnbox.engine

import io.github.sajadinmaker.vpnbox.data.Server
import io.github.sajadinmaker.vpnbox.data.VpnGate
import kotlin.random.Random
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.delay

/**
 * In-process tunnel simulator with CLI-identical pacing and phrasing.
 * `failures` makes the first N servers fail their handshake (each attempt
 * then takes a realistic ~6 s), after which a server connects in ~4 s.
 * This keeps every UI state — connecting, failing, recovered — reachable
 * without a network, and lets the tests drive the whole state machine.
 */
class SimulatedEngine(
    private var failures: Int = 0,
    private val rng: Random = Random.Default,
) : TunnelEngine {

    private val _events = MutableSharedFlow<EngineEvent>(extraBufferCapacity = 64)
    override val events: SharedFlow<EngineEvent> = _events.asSharedFlow()

    private suspend fun emit(e: EngineEvent) {
        _events.emit(e)
    }

    override suspend fun start(server: Server, keepalive: Pair<Int, Int>): Result<Unit> {
        val seconds = if (keepalive.first > 0 && keepalive.second > 0) {
            "ping ${keepalive.first} · ping-exit ${keepalive.second}"
        } else {
            "probe off"
        }
        emit(EngineEvent.Log("launching tunnel ($seconds) …"))
        val fail = failures > 0
        if (fail) failures--
        if (fail) {
            delay(6_000L)                                 // realistic failed handshake
            val bad = pickBadMarker()
            emit(EngineEvent.Log("× $bad"))
            emit(EngineEvent.Log(
                "volunteer servers are dynamic — VPN Gate entries may vanish"))
            emit(EngineEvent.HandshakeFailed(listOf(bad)))
            return Result.failure(VpnGate.VpnGateError("handshake failed"))
        }
        delay(4_000L)                                     // realistic handshake time
        emit(EngineEvent.Log("Initialization Sequence Completed"))
        emit(EngineEvent.HandshakeOk)
        return Result.success(Unit)
    }

    private fun pickBadMarker(): String {
        val candidates = VpnGate.FAIL_MARKERS.filter {
            it in listOf("Connection refused", "Connection timed out",
                         "No route to host", "Cannot resolve host")
        }
        return candidates[rng.nextInt(candidates.size)]
    }

    override fun stop() {
        // no-op: the simulated tunnel has no process to tear down
    }
}
