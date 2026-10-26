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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Android-side tunnel skeleton. VpnService is the only sanctioned way to
 * own the tun interface without root — this service is wired into the
 * manifest with `android.net.VpnService` action + `specialUse` foreground
 * type and owns:
 *   - the VPN-consent flow (VpnService.prepare before every start),
 *   - a persistent, in-aesthetic notification while the tunnel runs,
 *   - the (seam) hooks where the ics-openvpn/OpenVPN3 core will plug in:
 *     `onStartTunnel()` mounts the profile onto the tun fd, and its
 *     lifecycle callback emits `Down` to the app through [tunnelUp].
 *
 * Nothing here invents data: until the core lands, the UI runs the
 * SimulatedEngine and this service stays dormant-but-compileable.
 */
class VpnboxVpnService : VpnService() {

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                ServiceCompat.startForeground(
                    this, NOTIF_ID, buildNotification(),
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
                )
                tunnelUp.value = true
            }
            ACTION_DISCONNECT -> {
                tunnelUp.value = false
                ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
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
            .setContentTitle("vpnbox — tunnel up")
            .setContentText("full-tunnel over a volunteer relay")
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    // ---- the seam -----------------------------------------------------------

    /** TODO(ics-openvpn): read the built profile, Builder().addAddress/push
     * etc., attach the openvpn session to this fd. */
    private fun onStartTunnel(): Unit = TODO("openvpn core lands here")

    companion object {
        const val ACTION_CONNECT = "io.github.sajadinmaker.vpnbox.CONNECT"
        const val ACTION_DISCONNECT = "io.github.sajadinmaker.vpnbox.DISCONNECT"
        const val CHANNEL_ID = "vpnbox-tunnel"
        const val NOTIF_ID = 42

        /** Single source of truth for "is the (real) tunnel foregrounded". */
        val tunnelUp = MutableStateFlow(false)
    }
}
