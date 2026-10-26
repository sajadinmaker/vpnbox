package io.github.sajadinmaker.vpnbox

import io.github.sajadinmaker.vpnbox.data.SessionIntent
import io.github.sajadinmaker.vpnbox.data.SessionStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class SessionStoreTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun upIntent() = SessionIntent(
        country = "JP", city = null, proto = "udp", ping = 10, pingExit = 60,
    )

    @Test
    fun `roundtrips the intent`() {
        val f = tmp.newFolder()
        val store = SessionStore(java.io.File(f, "session.json"))
        store.save(upIntent())
        val loaded = store.load()
        assertEquals("JP", loaded?.country)
        assertEquals(false, loaded?.recovery)
    }

    @Test
    fun `disconnect writes the tombstone but keeps the intent — watchdog sees it`() {
        val store = SessionStore(java.io.File(tmp.newFolder(), "session.json"))
        store.save(upIntent())
        val before = System.currentTimeMillis()
        store.stop(store.load()!!)
        val after = store.load()!!
        assertTrue(after.stopped)
        assertTrue(after.stoppedAt >= before)
        assertEquals("JP", after.country)      // intent survives the tombstone
    }

    @Test
    fun `missing or malformed session files read as no session`() {
        val dir = tmp.newFolder()
        assertNull(SessionStore(java.io.File(dir, "none.json")).load())
        val bad = java.io.File(dir, "garbage.json")
        bad.writeText("!!!")
        assertNull(SessionStore(bad).load())
    }
}
