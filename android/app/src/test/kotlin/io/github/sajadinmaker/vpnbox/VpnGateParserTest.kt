package io.github.sajadinmaker.vpnbox

import io.github.sajadinmaker.vpnbox.data.CacheStore
import io.github.sajadinmaker.vpnbox.data.Server
import io.github.sajadinmaker.vpnbox.data.ServerCache
import io.github.sajadinmaker.vpnbox.data.VpnGateParser
import java.io.File
import java.util.Base64
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

private const val HEADER =
    "#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort," +
        "NumVpnSessions,Uptime,LogType,Operator,OpenVPN_ConfigData_Base64\n"

/** A config padded past the 200-char gate so the row survives parsing. */
private fun cfg(vararg lines: String): String {
    val core = lines.joinToString("\n")
    val filler = "\n# " + "x".repeat(220)
    return core + filler
}

private fun row(host: String, ip: String, ping: String, speed: String,
                country: String, cc: String, cfgText: String): String {
    val b64 = Base64.getEncoder().encodeToString(cfgText.toByteArray())
    return b64Row(host, ip, ping, speed, country, cc, b64)
}

private fun b64Row(host: String, ip: String, ping: String, speed: String,
                   country: String, cc: String, b64: String): String {
    return listOf(host, ip, "1000", ping, speed, country, cc, "3", "90000",
                  "-", "x", b64).joinToString(",")
}

class VpnGateParserTest {

    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun `parses rows and derives proto and port from the embedded config`() {
        val csv = HEADER +
            row("v1", "203.0.113.1", "7", "5000", "Japan", "JP",
                cfg("dev tun", "remote vpn-test 1596", "proto udp")) + "\n" +
            row("v2", "203.0.113.2", "9", "4000", "Japan", "JP",
                cfg("dev tun", "remote vpn-test 1194")) + "\n"
        val servers = VpnGateParser.parse(csv)
        assertEquals(2, servers.size)
        assertEquals("v1", servers[0].host)
        assertEquals("203.0.113.1", servers[0].ip)
        assertEquals("udp", servers[0].proto)     // explicit in profile
        assertEquals("1596", servers[0].port)
        assertEquals("Japan", servers[0].country)
        assertEquals("JP", servers[0].cc)          // normalized upper
        assertEquals("udp", servers[1].proto)      // default when absent
    }

    @Test
    fun `tcp-client normalizes to tcp and junk columns read as zero`() {
        val csv = HEADER +
            row("v", "203.0.113.9", "not-a-number", "broken", "Japan", "jp",
                cfg("dev tun", "remote vpn-test 1194", "proto tcp-client"))
        val s = VpnGateParser.parse(csv).single()
        assertEquals(0L, s.ping)
        assertEquals(0L, s.speed)
        assertEquals("tcp", s.proto)
    }

    @Test
    fun `short profiles are skipped like the CLI does`() {
        val csv = HEADER +
            row("a", "203.0.113.4", "5", "5", "Japan", "JP",
                "dev tun\nremote vpn-test 1194\n")
        assertTrue(VpnGateParser.parse(csv).isEmpty())
    }

    @Test
    fun `undecodable profiles are skipped, not crashed on`() {
        val csv = HEADER +
            b64Row("b", "203.0.113.5", "5", "5", "Japan", "JP",
                   "!!! not base64 !!!".repeat(12))
        assertTrue(VpnGateParser.parse(csv).isEmpty())
    }

    @Test
    fun `framing markers header-only bodies and malformed data fail cleanly`() {
        assertTrue(runCatching {
            VpnGateParser.parse("* softether marker\n").isEmpty()
        }.isFailure)                                   // no header → fail loudly
        runCatching {
            VpnGateParser.parse("#Wrong,Header\n1,2,3,4,5,6,7,8,9,10,11,12\n")
        }.onSuccess { v ->
            // tolerated: header present, but bad row count yields nothing
            assertTrue(v.isEmpty())
        }
        assertTrue(
            VpnGateParser.parse(
                HEADER + row("c", "203.0.113.6", "5", "5", "Japan", "JP",
                             cfg("dev tun")) + "\n",
            ).isNotEmpty(),
        )
    }

    @Test
    fun `cache survives a roundtrip and rejects malformed content`() {
        val parsed = VpnGateParser.parse(
            HEADER + row("z", "203.0.113.3", "15", "600", "Japan", "JP",
                         cfg("dev tun", "remote z 1194")))
        val fresh = ServerCache(4242L, parsed)
        val dir = tmp.newFolder()
        val store = CacheStore(File(dir, "c.json"))
        store.save(fresh)
        assertEquals(4242L, store.load()?.updated)
        assertEquals("z", store.load()?.servers?.first()?.host)
        File(dir, "garbage.json").writeText("junk!!!")
        val bad = CacheStore(File(dir, "garbage.json"))
        assertTrue(bad.load() == null)
    }
}
