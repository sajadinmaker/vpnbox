package io.github.sajadinmaker.vpnbox.engine

import android.content.Context
import android.content.Intent
import android.net.VpnService
import androidx.core.content.ContextCompat
import io.github.sajadinmaker.vpnbox.data.Server
import io.github.sajadinmaker.vpnbox.data.buildConf
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.withTimeoutOrNull

/**
 * TunnelEngine over the real OpenVPN 3 core in [VpnboxVpnService].
 *
 * `start()` mirrors the CLI's launch()+wait_ready(): it pushes the
 * CLI-twin profile (`Domain.buildConf`) into the service and returns only
 * after the handshake has settled (ok / failed / ~45 s timeout). The
 * tunnel then keeps running in the service; later `Down` events arrive
 * through [events] and feed the watchdog.
 */
class OpenVpn3Engine(private val context: Context) : TunnelEngine {

    override val events: Flow<EngineEvent> get() = EngineBus.events

    override suspend fun start(server: Server, keepalive: Pair<Int, Int>): Result<Unit> {
        val profile = buildConf(server, keepalive)
        val label = serverLabel(server)

        // reset any handshake verdict from a previous attempt
        EngineBus.handshake.value = null

        val intent = Intent(context, VpnboxVpnService::class.java).apply {
            action = VpnboxVpnService.ACTION_CONNECT
            putExtra(VpnboxVpnService.EXTRA_PROFILE, profile)
            putExtra(VpnboxVpnService.EXTRA_SERVER_LABEL, label)
        }
        ContextCompat.startForegroundService(context, intent)

        val settled = withTimeoutOrNull(HANDSHAKE_TIMEOUT_MS) {
            EngineBus.handshake.filterNotNull().first()
        }
        return when (settled) {
            is EngineEvent.HandshakeOk -> Result.success(Unit)
            is EngineEvent.HandshakeFailed -> Result.failure(
                VpnGateEngineError(settled.excerpt.joinToString("\n")),
            )
            else -> Result.failure(VpnGateEngineError("handshake timed out"))
        }
    }

    override fun stop() {
        val intent = Intent(context, VpnboxVpnService::class.java).apply {
            action = VpnboxVpnService.ACTION_DISCONNECT
        }
        runCatching { context.startService(intent) }
    }

    /** Does the app still hold the user's VPN permission? */
    fun vpnConsentRequired(): Boolean = VpnService.prepare(context) != null

    /** The system consent dialog to launch, or null when already granted. */
    fun vpnConsentIntent(): Intent? = VpnService.prepare(context)

    private fun serverLabel(r: Server): String =
        buildString {
            append(r.country)
            if (r.city.isNotBlank()) {
                append(" · ")
                append(r.city)
            }
            append(" (")
            append(r.proto.uppercase())
            append(")")
        }

    class VpnGateEngineError(message: String) : Exception(message)

    companion object {
        private const val HANDSHAKE_TIMEOUT_MS = 45_000L
    }
}
