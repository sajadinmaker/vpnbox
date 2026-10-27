package io.github.sajadinmaker.vpnbox.engine

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import androidx.core.app.ServiceCompat
import io.github.sajadinmaker.vpnbox.MainActivity
import io.github.sajadinmaker.vpnbox.R
import io.github.sajadinmaker.vpnbox.data.Server
import java.net.InetAddress
import java.util.ArrayDeque
import kotlinx.coroutines.flow.asStateFlow
import net.openvpn.ovpn3.ClientAPI_Config
import net.openvpn.ovpn3.ClientAPI_EvalConfig
import net.openvpn.ovpn3.ClientAPI_Event
import net.openvpn.ovpn3.ClientAPI_LogInfo
import net.openvpn.ovpn3.ClientAPI_OpenVPNClient
import net.openvpn.ovpn3.ClientAPI_StringVec
import net.openvpn.ovpn3.DnsOptions
import net.openvpn.ovpn3.DnsServer

/**
 * Android side of the real tunnel: a [VpnService] hosted exactly like the
 * CLI's daemon — the OpenVPN 3 core runs in-process on its own thread, and
 * asks this service for the tun fd through the TunBuilder callbacks.
 *
 * All state changes cross [EngineBus]; profile content is the CLI-twin
 * output of `Domain.buildConf()` (windows-directive stripping, full-tunnel
 * `redirect-gateway def1` + `block-ipv6`, never emitting `ping 0`).
 *
 * The notification is the CLI's status line replacement: persistent while
 * the tunnel runs; the core's own events drive the connect/restore UX.
 */
class VpnboxVpnService : VpnService() {

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                EngineBus.markStarting(
                    intent.getStringExtra(EXTRA_SERVER_LABEL) ?: "",
                )
                EngineBus.markRunning(true)
                ServiceCompat.startForeground(
                    this, NOTIF_ID, buildNotification(),
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
                )
                val profile = intent.getStringExtra(EXTRA_PROFILE).orEmpty()
                if (profile.isBlank()) {
                    handleDisconnect()
                    return START_NOT_STICKY
                }
                startCore(profile)
            }
            ACTION_DISCONNECT -> {
                EngineBus.currentClient()?.stop()
                EngineBus.emit(EngineEvent.Log("Disconnect requested"))
                handleDisconnect()
            }
            else -> handleDisconnect()
        }
        // START_NOT_STICKY: a process death kills the tun (and the fd); the
        // watchdog / relaunch-restore logic re-derives tunnel truth instead
        // of resurrecting a half-built service like a stale profile would
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        EngineBus.currentClient()?.stop()
        EngineBus.currentClientClear()
        EngineBus.markRunning(false)
        super.onDestroy()
    }

    private fun startCore(profile: String) {
        stopCoreQuiet()
        val client = TunnelClient(this, profile, EngineBus.serverLabel.value)
        EngineBus.attach(client)
        Thread(client, "vpnbox-openvpn3").start()
    }

    private fun stopCoreQuiet() {
        EngineBus.currentClient()?.let { c ->
            runCatching { c.stop() }
        }
        EngineBus.currentClientClear()
    }

    private fun handleDisconnect() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
        EngineBus.markRunning(false)
    }

    private fun ensureChannel() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID, "vpnbox tunnel", NotificationManager.IMPORTANCE_LOW,
            ).apply { setShowBadge(false) },
        )
    }

    private fun buildNotification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("vpnbox — tunnel active")
            .setContentText(
                EngineBus.serverLabel.value.ifBlank {
                    "Traffic is routed through VPN Gate"
                },
            )
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    /**
     * The OpenVPN 3 client thread. Callbacks are the TunBuilder bridge that
     * schwarze/ics-openvpn documents as the integration contract: the core
     * drives, this class answers with Android's [VpnService.Builder].
     */
    private class TunnelClient(
        private val service: VpnboxVpnService,
        private val profile: String,
        private val label: String,
    ) : ClientAPI_OpenVPNClient(), EngineBus.ClientHandle, Runnable {

        private var builder: android.net.VpnService.Builder? = null
        private val logTail = ArrayDeque<String>(TAIL_KEEP)
        private var gotConnected = false

        override fun run() {
            val config = ClientAPI_Config()
            config.setContent(profile)
            config.setTunPersist(true)
            config.setCompressionMode("asym")
            config.setInfo(true)
            config.setAllowLocalLanAccess(false)
            config.setSsoMethods("openurl,webauth,crtext")

            val ec = eval_config(config)
            if (ec.getError()) {
                EngineBus.emit(EngineEvent.Log("× Config rejected: ${ec.getMessage()}"))
                EngineBus.emit(EngineEvent.HandshakeFailed(listOf(ec.getMessage())))
                finishThread()
                return
            }
            val status = connect()
            if (status.getError()) {
                EngineBus.emit(
                    EngineEvent.Log("× openvpn exited: ${status.getStatus()}: ${status.getMessage()}"),
                )
                if (!gotConnected) {
                    EngineBus.emit(
                        EngineEvent.HandshakeFailed(excerpt()),
                    )
                } else {
                    EngineBus.emit(EngineEvent.Down)
                }
            } else if (gotConnected) {
                // graceful stop from the user (or core); teardown happened
                EngineBus.emit(EngineEvent.Down)
            }
            finishThread()
        }

        private fun finishThread() {
            if (EngineBus.currentClient() === this) {
                EngineBus.currentClientClear()
            }
            EngineBus.markRunning(false)
        }

        private fun excerpt(): List<String> = ArrayList(logTail)

        // ---- openvpn3 → Android tun bridge --------------------------------

        override fun tun_builder_new(): Boolean {
            builder = service.Builder()
            return builder != null
        }

        override fun tun_builder_set_mtu(mtu: Int): Boolean {
            builder?.setMtu(mtu)
            return true
        }

        override fun tun_builder_set_remote_address(address: String, ipv6: Boolean): Boolean {
            // no caller-visible action: connect() already binds the socket;
            // and protect() is applied from socket_protect()
            return true
        }

        override fun tun_builder_set_layer(layer: Int): Boolean = layer == 3

        override fun tun_builder_add_address(
            address: String,
            prefix_length: Int,
            gateway: String,
            ipv6: Boolean,
            net30: Boolean,
        ): Boolean {
            builder?.addAddress(address, prefix_length)
            return true
        }

        override fun tun_builder_reroute_gw(
            ipv4: Boolean,
            ipv6: Boolean,
            flags: Long,
        ): Boolean {
            if ((flags and emulateExcludeRoutes) != 0L) return true
            builder?.addRoute("0.0.0.0", 0)
            if (ipv6) builder?.addRoute("::", 0)
            return true
        }

        override fun tun_builder_add_route(
            address: String,
            prefix_length: Int,
            metric: Int,
            ipv6: Boolean,
        ): Boolean {
            if (address == "remote_host") return false
            builder?.addRoute(address, prefix_length)
            return true
        }

        override fun tun_builder_exclude_route(
            address: String,
            prefix_length: Int,
            metric: Int,
            ipv6: Boolean,
        ): Boolean {
            // local-LAN exclusion stays off (like the CLI's full-tunnel
            // redirect-gateway def1 choice); allowLocalLanAccess=false above
            return true
        }

        override fun tun_builder_set_dns_options(dns: DnsOptions): Boolean {
            var added = false
            for (d in dns.getSearch_domains()) {
                if (d.getDomain().isNotBlank()) {
                    builder?.addSearchDomain(d.getDomain())
                }
            }
            val sorted = java.util.TreeMap<Int, DnsServer>(dns.getServers())
            for ((_, server) in sorted) {
                for (a in server.getAddresses()) {
                    val port = a.getPort()
                    if (port != 0L && port != 53L) continue
                    val addr = a.getAddress()
                    if (addr.isBlank()) continue
                    runCatching {
                        // address strings are literals; no resolver involved
                        builder?.addDnsServer(InetAddress.getByName(addr))
                        added = true
                    }
                }
                if (added) return true
            }
            if (!added) {
                EngineBus.emit(EngineEvent.Log("× server provides no usable DNS — refusing"))
                return false
            }
            return true
        }

        override fun tun_builder_get_local_networks(ipv6: Boolean): ClientAPI_StringVec {
            // full tunnel: nothing excluded from routing (mirrors CLI's
            // redirect-gateway def1 + block-ipv6 hardening)
            return ClientAPI_StringVec()
        }

        override fun tun_builder_establish(): Int {
            val b = builder ?: return -1
            b.setSession(label.ifBlank { "vpnbox" })
            val fd = b.establish() ?: return -1
            return fd.detachFd()
        }

        override fun socket_protect(socket: Int, remote: String, ipv6: Boolean): Boolean =
            service.protect(socket)

        // ---- core lifecycle events -----------------------------------------

        override fun log(arg: ClientAPI_LogInfo) {
            var msg = arg.getText()
            while (msg.endsWith("\n")) {
                msg = msg.dropLast(1)
            }
            if (msg.isNotBlank()) {
                synchronized(logTail) {
                    if (logTail.size == TAIL_KEEP) logTail.removeFirst()
                    logTail.addLast(msg)
                }
                EngineBus.emit(EngineEvent.Log(msg))
            }
        }

        override fun event(ev: ClientAPI_Event) {
            val name = ev.getName()
            val info = ev.getInfo()
            when {
                name == "CONNECTED" -> {
                    gotConnected = true
                    EngineBus.emit(EngineEvent.HandshakeOk)
                }
                ev.getError() -> {
                    // handshake-time failure (auth refused, resolve, timeout)
                    EngineBus.emit(
                        EngineEvent.Log("× $name: $info"),
                    )
                    if (!gotConnected) {
                        EngineBus.emit(EngineEvent.HandshakeFailed(excerpt()))
                    } else {
                        EngineBus.emit(EngineEvent.Down)
                    }
                }
                name == "DISCONNECTED" -> {
                    if (gotConnected) EngineBus.emit(EngineEvent.Down)
                }
                else -> EngineBus.emit(
                    EngineEvent.Log(
                        if (info.isNotBlank()) "$name: $info" else name,
                    ),
                )
            }
        }

        override fun stop() {
            // safe from any thread; the core posts the stop internally
            runCatching { super.stop() }
        }

        companion object {
            private const val TAIL_KEEP = 12
            private const val emulateExcludeRoutes = 1L shl 16
        }
    }

    companion object {
        const val ACTION_CONNECT = "io.github.sajadinmaker.vpnbox.CONNECT"
        const val ACTION_DISCONNECT = "io.github.sajadinmaker.vpnbox.DISCONNECT"
        const val EXTRA_PROFILE = "profile"
        const val EXTRA_SERVER_LABEL = "serverLabel"
        const val CHANNEL_ID = "vpnbox-tunnel"
        const val NOTIF_ID = 42
    }
}
