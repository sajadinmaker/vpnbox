package io.github.sajadinmaker.vpnbox.data

import kotlinx.serialization.Serializable

/** One server from the VPN Gate CSV — exact field-for-field twin of the CLI. */
@Serializable
data class Server(
    val host: String,
    val ip: String,
    val score: Long,
    val ping: Long,
    val speed: Long,
    val country: String,
    val cc: String,
    val sessions: Long,
    val uptime: Long,
    val log: String,
    val operator: String,
    val proto: String,   // "udp" or "tcp"
    val port: String,    // "" when unknown
    val cfg: String,     // embedded OpenVPN config (base64-decoded)
    // filled in by the best-effort ip-api enrichment pass
    var city: String = "",
    var isp: String = "",
    var region: String = "",
    var lat: Double? = null,
    var lon: Double? = null,
)

/** A cached server list, so the app works offline after the first refresh. */
@Serializable
data class ServerCache(
    val updated: Long,
    val servers: List<Server>,
)
