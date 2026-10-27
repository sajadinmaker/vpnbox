package io.github.sajadinmaker.vpnbox.engine

import io.github.sajadinmaker.vpnbox.data.Server

/** Events a tunnel engine emits while connecting, running, or dying. */
sealed interface EngineEvent {
    /** One log line, phrased exactly like the CLI's terminal output. */
    data class Log(val line: String) : EngineEvent

    /** Marker: this attempt's handshake succeeded (routes settled). */
    data object HandshakeOk : EngineEvent

    /** Marker: handshake failed; `excerpt` holds the failing log lines. */
    data class HandshakeFailed(val excerpt: List<String>) : EngineEvent

    /** Marker: an established tunnel died (volunteer servers do). */
    data object Down : EngineEvent
}

/**
 * The engine seam. Production implementation: [OpenVpn3Engine], which hosts
 * the real OpenVPN 3 core inside `VpnboxVpnService`.
 */
interface TunnelEngine {
    val events: kotlinx.coroutines.flow.Flow<EngineEvent>

    /** Attempt to establish the tunnel for `server`. Returns when the
     * handshake has settled (ok or failed) — mirrors launch()+wait_ready(). */
    suspend fun start(server: Server, keepalive: Pair<Int, Int>): Result<Unit>

    fun stop()
}
