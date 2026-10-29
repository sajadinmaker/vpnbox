package io.github.sajadinmaker.vpnbox

import io.github.sajadinmaker.vpnbox.data.Server
import io.github.sajadinmaker.vpnbox.data.UserError
import io.github.sajadinmaker.vpnbox.data.backoffSeconds
import io.github.sajadinmaker.vpnbox.data.buildConf
import io.github.sajadinmaker.vpnbox.data.checkPingSettings
import io.github.sajadinmaker.vpnbox.data.rankKey
import io.github.sajadinmaker.vpnbox.data.selectServers
import io.github.sajadinmaker.vpnbox.data.validateArgs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private fun server(
    ip: String, ping: Long = 20, speed: Long = 1_000_000,
    proto: String = "udp", cc: String = "JP", country: String = "Japan",
    city: String = "Tokyo", score: Long = 1000, host: String = "vpn-$ip",
): Server = Server(
    host = host, ip = ip, score = score, ping = ping, speed = speed,
    country = country, cc = cc, sessions = 3, uptime = 90_000, log = "-",
    operator = "x", proto = proto, port = "1194",
    cfg = "dev tun\nremote vpn.test 1194\n", city = city,
)

class DomainTest {

    @Test
    fun `rank puts responsive udp first then speed then ping then score`() {
        val slow = server("1", proto = "tcp")
        val fastUdp = server("2")
        val noPingData = server("3", ping = 0)
        val slowerUdp = server("4", speed = 100)
        val ranked = listOf(slow, fastUdp, noPingData, slowerUdp)
            .sortedWith(rankKey).map { it.ip }
        assertEquals(listOf("2", "4", "1", "3"), ranked)
    }

    @Test
    fun `selectServers narrows by exact code then by country name`() {
        val pool = listOf(
            server("1", cc = "JP", country = "Japan"),
            server("2", cc = "US", country = "United States"),
        )
        val byCode = selectServers(pool, "jp").first
        assertEquals(listOf("1"), byCode.map { it.ip })
        val (byName, why) = selectServers(pool, "japan")
        assertTrue(byName.map { it.ip } == listOf("1"))
        assertEquals("", why)
    }

    @Test
    fun `selectServers city miss lists known cities`() {
        val (out, why) = selectServers(listOf(server("1")), "JP", "osaka")
        assertTrue(out.isEmpty())
        assertTrue(why.contains("No servers in JP match city 'osaka'"))
        assertTrue(why.contains("Tokyo"))
    }

    @Test
    fun `validateArgs rejects args that would select zero servers`() {
        assertThrows("Skip must be 0 or greater") { validateArgs(-1, null, 3, 10, 60) }
        assertThrows("Index must be 1 or greater") { validateArgs(0, 0, 3, 10, 60) }
        assertThrows("Retry count must be 1 or greater") { validateArgs(0, null, 0, 10, 60) }
    }

    @Test
    fun `ping settings zero means probe off and exits must outlive pings`() {
        assertEquals(0, checkPingSettings(0, 60))
        assertEquals(60, checkPingSettings(10, 60))
        assertThrows("exit <= ping") { checkPingSettings(60, 60) }
        assertThrows("negative ping") { checkPingSettings(-1, 60) }
        assertThrows("negative exit") { checkPingSettings(10, -1) }
    }

    @Test
    fun `buildConf strips windows directives and never emits ping zero`() {
        val s = server("5").copy(
            cfg = "dev tun\nremote vpn.test 1194\nwin-sys log\nroute-method exe\n")
        val conf = buildConf(s, keepalive = Pair(0, 60))
        assertFalse(conf.contains("win-sys"))
        assertFalse(conf.contains("ping 0"))
        assertFalse(conf.contains("ping-exit"))
        assertTrue(conf.contains("redirect-gateway def1"))
        val withPing = buildConf(s, keepalive = Pair(10, 60))
        assertTrue(withPing.contains("\nkeepalive 10 60\n"))
        assertFalse(withPing.contains("ping-exit"))
    }

    @Test
    fun `backoff doubles with a 300s cap`() {
        assertEquals(listOf(30L, 60L, 120L, 240L, 300L, 300L),
                     (1..6).map { backoffSeconds(it) })
    }

    private fun assertThrows(
        hint: String,
        block: () -> Unit,
    ) {
        try {
            block()
        } catch (e: UserError) {
            return
        }
        throw AssertionError("expected UserError: $hint")
    }
}
