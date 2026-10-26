package io.github.sajadinmaker.vpnbox.data

import java.util.Base64

/** Parser for the VPN Gate CSV list — semantic twin of parse_list() in the CLI. */
object VpnGateParser {
    private val protoInConfig = Regex("""^\s*proto\s+(\S+)""", RegexOption.MULTILINE)
    private val remoteInConfig = Regex("""^\s*remote\s+(\S+)\s+(\d+)""", RegexOption.MULTILINE)

    private val wanted = listOf(
        "hostname", "ip", "score", "ping", "speed",
        "countrylong", "countryshort", "numvpnsessions", "uptime",
        "logtype", "operator", "openvpn_configdata_base64",
    )

    fun parse(text: String): List<Server> {
        val body = mutableListOf<String>()
        var header: List<String>? = null
        for (line in text.lineSequence()) {
            val t = line.trimStart()
            if (t.startsWith("*")) continue            // softether framing markers
            if (header == null) {
                if (t.startsWith(VpnGate.HOSTNAME_HEADER)) {
                    header = t.removePrefix("#").split(",").map { it.trim().lowercase() }
                }
                continue
            }
            if (t.startsWith("#") || t.isBlank()) continue
            body.add(line.trimEnd('\r'))
        }
        val hdr = header ?: throw VpnGate.VpnGateError("unrecognized VPN Gate response format.")
        val idx = wanted.associateWith { hdr.indexOf(it) }
        val missing = idx.filterValues { it < 0 }.keys
        if (missing.isNotEmpty()) {
            throw VpnGate.VpnGateError("VPN Gate API columns missing: $missing")
        }
        val out = mutableListOf<Server>()
        for (row in body) {
            try {
                val fields = row.split(",")
                if (fields.size < hdr.size - 2) continue
                val b64 = fields[idx["openvpn_configdata_base64"]!!].trim()
                if (b64.length < 200) continue           // no usable OpenVPN profile
                val cfg = try {
                    String(Base64.getDecoder().decode(b64), Charsets.UTF_8)
                } catch (e: IllegalArgumentException) {
                    continue
                }
                var proto = "udp"
                val pm = protoInConfig.find(cfg)
                if (pm != null) proto = pm.groupValues[1].replace("tcp-client", "tcp")
                var port = ""
                val rm = remoteInConfig.find(cfg)
                if (rm != null) port = rm.groupValues[2]
                fun fld(name: String) = fields[idx[name]!!].trim()
                out.add(Server(
                    host = fld("hostname"),
                    ip = fld("ip"),
                    score = quietLong(fld("score")),
                    ping = quietLong(fld("ping")),
                    speed = quietLong(fld("speed")),
                    country = fld("countrylong"),
                    cc = fld("countryshort").uppercase(),
                    sessions = quietLong(fld("numvpnsessions")),
                    uptime = quietLong(fld("uptime")),
                    log = fld("logtype"),
                    operator = fld("operator"),
                    proto = proto,
                    port = port,
                    cfg = cfg,
                ))
            } catch (e: Exception) {
                continue                                  // keep going, same as CLI
            }
        }
        return out
    }

    /** Same tolerance as the CLI's quiet_int(): junk columns read as zero. */
    fun quietLong(s: String): Long = s.trim().toLongOrNull() ?: 0L
}
