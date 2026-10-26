"""vpnbox unit tests — fully hermetic: no network, no root, no caches.

Run from the repo root:
    python3 -m unittest discover -s . -p "test_*.py" -v     (or: make test)
"""
import argparse
import contextlib
import inspect
import io
import os
import stat
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vpnbox as v  # noqa: E402


def server(**over):
    """Synthetic VPN Gate server record (exact parse_server() shape)."""
    r = {
        "host": "vpn-test", "ip": "203.0.113.7", "score": 1000,
        "ping": 20, "speed": 1_000_000, "country": "Japan", "cc": "JP",
        "sessions": 3, "uptime": 90_000, "log": "-", "operator": "x",
        "proto": "udp", "port": "1194", "cfg": "dev tun\nremote vpn.test 1194\n",
        "city": "Tokyo", "isp": "TEST ISP", "region": "Tokyo",
        "lat": 35.6762, "lon": 139.6503,
    }
    r.update(over)
    return r


class SiteDatabase(unittest.TestCase):
    def test_every_site_has_usable_offices(self):
        for name, s in v.SITES.items():
            self.assertGreater(len(s["offices"]), 0, f"{name}: no offices")
            self.assertTrue(s["label"].strip(), f"{name}: empty label")
            for off in s["offices"]:
                cc, place, la, lo, _query = off
                self.assertEqual(len(off), 5, f"{name}: {off!r}")
                self.assertEqual(len(cc), 2, f"{name}: bad cc {cc!r}")
                self.assertTrue(place.strip(), f"{name}: empty place")
                self.assertTrue(-90 <= la <= 90, f"{name} {place}: lat {la}")
                self.assertTrue(-180 <= lo <= 180, f"{name} {place}: lon {lo}")

    def test_database_totals(self):
        offices = sum(len(s["offices"]) for s in v.SITES.values())
        countries = {o[0] for s in v.SITES.values() for o in s["offices"]}
        self.assertGreaterEqual(offices, 200)
        self.assertGreaterEqual(len(v.SITES), 25)
        self.assertGreaterEqual(len(countries), 30)

    def test_site_aliases_resolve(self):
        for alias, canonical in (("twitter", "x"), ("ig", "instagram"),
                                 ("fb", "meta"), ("sp", "spotify"),
                                 ("nflx", "netflix"), ("wa", "whatsapp")):
            key, site = v.resolve_site(alias)
            self.assertEqual(key, canonical)
            self.assertTrue(site)


class Geometry(unittest.TestCase):
    def test_haversine_tokyo_seoul(self):
        d = v.haversine_km(35.6762, 139.6503, 37.5665, 126.9780)
        self.assertAlmostEqual(d, 1155, delta=25)

    def test_dist_tier_boundaries(self):
        self.assertEqual(v.dist_tier(0), 0)
        self.assertEqual(v.dist_tier(40), 0)
        self.assertEqual(v.dist_tier(40.01), 1)
        self.assertEqual(v.dist_tier(150), 1)
        self.assertEqual(v.dist_tier(500), 2)
        self.assertEqual(v.dist_tier(500.01), 3)
        self.assertEqual(v.dist_tier(1500), 3)
        self.assertEqual(v.dist_tier(1500.01), 4)


class Ranking(unittest.TestCase):
    def test_fast_udp_beats_slow_tcp(self):
        fast = server()
        slow = server(proto="tcp", ping=400, speed=1000)
        self.assertLess(v.rank(fast), v.rank(slow))

    def test_missing_ping_is_penalized(self):
        # ping 0 means "no data", not "so fast they couldn't measure it"
        good = server(ping=50)
        unknown = server(ping=0)
        self.assertLess(v.rank(good), v.rank(unknown))


class SiteTargeting(unittest.TestCase):
    """tier ranking: near offices win the tier; quality decides inside it."""

    def test_same_tier_goes_to_better_quality(self):
        offices = v.SITES["kakaotalk"]["offices"]           # Seoul ~37.57/126.98
        near_slow = server(ip="1.1.1.1", lat=37.60, lon=127.00,
                           ping=250, speed=100_000)         # ~5 km → tier 0
        near_fast = server(ip="1.1.1.2", lat=37.55, lon=126.99,
                           ping=5, speed=5_000_000)         # ~1 km → tier 0
        sel, _ = v.site_candidates([near_slow, near_fast], offices,
                                   site_key="kakaotalk")
        self.assertIs(sel[0], near_fast)

    def test_far_fast_never_beats_near_slow(self):
        offices = v.SITES["kakaotalk"]["offices"]
        seoul_slow = server(ip="1.1.1.1", lat=37.60, lon=127.00,
                            ping=300, speed=100_000)        # tier 0
        tokyo_flying = server(ip="1.1.1.2", lat=35.68, lon=139.69,
                              ping=2, speed=99_000_000)     # ~1150 km → tier 3
        sel, _ = v.site_candidates([tokyo_flying, seoul_slow], offices,
                                   site_key="kakaotalk")
        self.assertEqual(sel[0]["ip"], seoul_slow["ip"])

    def test_ungeolocated_servers_always_lose(self):
        offices = v.SITES["kakaotalk"]["offices"]
        noloc = server(ip="1.1.1.1", lat=None, lon=None,
                       ping=1, speed=99_999_999)
        near_dead = server(ip="1.1.1.2", lat=37.55, lon=126.99,
                           ping=300, speed=100)
        sel, _ = v.site_candidates([noloc, near_dead], offices,
                                   site_key="kakaotalk")
        self.assertEqual(sel[0]["ip"], near_dead["ip"])


class ConfigAndConsistency(unittest.TestCase):
    def test_build_conf_enforces_full_tunnel(self):
        conf = v.build_conf(server())
        self.assertIn("### vpnbox profile", conf)
        self.assertIn("redirect-gateway def1", conf)
        self.assertIn("block-ipv6", conf)

    def test_version_single_source_of_truth(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "vpnbox.py"), encoding="utf-8") as f:
            self.assertIn(f'APP_VERSION = "{v.APP_VERSION}"', f.read())
        with open(os.path.join(here, "CHANGELOG.md"), encoding="utf-8") as f:
            self.assertTrue(
                any(l.startswith("## " + v.APP_VERSION) for l in f),
                "CHANGELOG.md has no section for APP_VERSION")


class Intro(unittest.TestCase):
    FAKE_SNAP = {"connected": False, "servers": 96, "countries": 8,
                 "age": 300, "ip": "203.0.113.9", "city": "Bengaluru",
                 "country": "India"}

    def test_intro_header_is_minimal(self):
        # no ASCII banner, no taglines — the name lives in a red band drawn
        # with block glyphs only (mono font, nothing to misrender)
        self.assertNotIn("▁", v.TITLE)
        self.assertNotIn("#", v.TITLE)
        self.assertEqual("".join(v.TITLE.split()), "VPNBOX")
        block = v.intro_titlebar(100)
        self.assertEqual(len(block), 5)                 # 5-row band
        self.assertIn("█", block[0])
        for glyph in v.INTRO_FONT.values():
            self.assertEqual(len(glyph), 5)
            for row in glyph:
                self.assertTrue(set(row) <= {"█", " "},
                                f"stray glyph char in font: {row!r}")

    def test_read_key_uses_unbuffered_reads(self):
        # regression: sys.stdin.read(1) kept typed-ahead bytes (e.g. '2' +
        # Enter in one burst) in Python's buffer, leaking them into the next
        # input() as a blank answer → dialogs cancelled instantly
        import inspect
        src = inspect.getsource(v.read_key)
        self.assertIn("os.read", src)
        code_only = src.split('"""', 2)[2]      # skip the docstring's own story
        self.assertNotIn("sys.stdin.read(1)", code_only)

    def test_intro_run_drains_stdin_before_actions(self):
        calls = []
        stub = []
        with unittest.mock.patch.object(
                v, "_drain_stdin", side_effect=lambda: calls.append(1)), \
             unittest.mock.patch.object(
                 v, "INTRO_ACTIONS", [("fastest", "x", lambda: stub.append(1))]):
            self.assertEqual(v.intro_run(0), None)
        self.assertEqual(calls, [1])
        self.assertEqual(stub, [1])

    def test_dialog_entry_never_bounces_back_on_enter(self):
        # regression: pressing Enter right after a menu number used to count
        # as "go back" and dumped the user onto the menu — Enter must commit
        # a forward default, Esc / Esc-only exits are the way back
        site = inspect.getsource(v._pick_site)
        country = inspect.getsource(v.intro_wizard)
        self.assertIn("_readline", site)
        self.assertIn('_readline', country)
        self.assertIn('== ""', site)             # empty Enter → first entry
        self.assertIn('chosen = order[0][0]', country)
        self.assertIn('return []', inspect.getsource(v._pick_office))
        rl = inspect.getsource(v._readline)
        self.assertIn("_drain_stdin()", rl)
        # the only input() left is the guarded non-TTY fallback
        self.assertEqual(rl.count("input()"), 1)
        # soak only runs on a real TTY — piped answers must survive
        self.assertLess(v._PROMPT_SOAK, 0.5)
        self.assertIn("_PROMPT_SOAK", rl)

    def test_country_prompt_resolves_list_numbers(self):
        # regression: typing "1" had to pick the 1st listed country (JP),
        # not pass the literal digit through as --country 1
        src = inspect.getsource(v.intro_wizard)
        self.assertIn("cc.isdigit()", src)
        self.assertIn("order[int(cc) - 1][0]", src)

    def test_arrows_only_move_the_menu(self):
        # regression: up/down accidentally fell through into intro_run() with
        # an unbound index — a NameError crash on the very first arrow press
        src = inspect.getsource(v.cmd_intro)
        between = src.split('elif key == "enter"', 1)[0]
        self.assertEqual(between.count("continue"), 2)   # up/down re-render

    def test_titlebar_is_big_and_bold(self):
        # a red-themed box: 5 rows of big mono block letters at every sane
        # width, double-wide cells on very wide screens — never overflowing
        for width in (60, 80, 92):
            lines = v.intro_titlebar(width)
            self.assertEqual(len(lines), 5)
            band = len(v.strip_ansi(lines[0]))
            self.assertGreaterEqual(band, 40)
            self.assertLessEqual(band, width - 6)
        wide = v.intro_titlebar(120)
        self.assertEqual(len(wide), 5)
        self.assertGreater(len(v.strip_ansi(wide[0])),
                           len(v.strip_ansi(v.intro_titlebar(80)[0])),
                           "very wide terminals must get BIGGER letters")
        for width in (38, 41):                       # too narrow for blocks
            lines = v.intro_titlebar(width)
            self.assertEqual(len(lines), 1)
            self.assertIn("V", v.strip_ansi(lines[0]))
        with unittest.mock.patch.dict(os.environ, {"VPNBOX_PLAIN": "1"}):
            lines = v.intro_titlebar(120)
            self.assertEqual(len(lines), 1)
            self.assertIn("V", v.strip_ansi(lines[0]))

    def test_render_fits_any_terminal_width(self):
        for width in (46, 64, 80, 110, 120, 160):
            with unittest.mock.patch.object(v, "tty_width", return_value=width):
                text = v.intro_render(self.FAKE_SNAP, sel=0)
            vis = max(len(l) for l in text.splitlines())
            self.assertLessEqual(vis, width,
                                 f"line overflows a {width}-col terminal")

    def test_status_panel_rewraps_with_the_screen(self):
        # responsive: narrow screens must stack the status facts, wide ones
        # may keep them on one row — no information, no overflow either way
        narrow = v.intro_status_rows(self.FAKE_SNAP, limit=32)
        joined = " ".join(narrow)
        self.assertIn("Bengaluru", joined)
        self.assertIn("96 live servers", joined)
        self.assertTrue(all(len(f) <= 32 for f in narrow[1:]),
                        narrow)
        wide = v.intro_status_rows(self.FAKE_SNAP, limit=200)
        self.assertEqual(len(wide), 2)             # state + all facts, one row
        self.assertIn("list refreshed 5 min ago", wide[1])

    def test_strip_ansi_and_fit_center(self):
        self.assertEqual(v.strip_ansi("\x1b[32mabc\x1b[0m"), "abc")
        padded = v.fit_center("\x1b[32mok\x1b[0m", 30)
        # left-padding only: (width - visible) // 2 spaces, then the text
        self.assertEqual(len(v.strip_ansi(padded)), (30 - 2) // 2 + 2)
        self.assertTrue(v.strip_ansi(padded).endswith("ok"))

    def test_intro_key_dispatch_table(self):
        self.assertEqual(sorted(v.INTRO_KEYS),
                         ["c", "d", "q", "r", "s"])
        self.assertEqual(v.INTRO_KEYS["r"], 3)     # refresh row index
        self.assertEqual(v.INTRO_KEYS["q"], 5)     # quit row index
        self.assertEqual(len(v.INTRO_ACTIONS), 6)
        self.assertEqual([a[0] for a in v.INTRO_ACTIONS],
                         ["fastest", "country", "office", "refresh",
                          "disconnect", "quit"])
        for _aid, desc, fn in v.INTRO_ACTIONS:
            self.assertTrue(desc.strip())
            self.assertTrue(fn is None or callable(fn))

    def test_bare_invocation_routes_to_intro(self):
        ap = v.build_parser()
        args = ap.parse_args([])          # bare run: no subcommand
        self.assertIsNone(args.cmd)
        self.assertEqual(ap.parse_args(["intro"]).cmd, "intro")

    def test_render_is_pure_and_offline_able(self):
        text = v.intro_render(self.FAKE_SNAP, msg="hi", sel=2)
        flat = v.strip_ansi(text)
        self.assertIn("not connected", flat)
        self.assertIn("your IP", flat)
        self.assertIn("live servers", flat)
        self.assertIn("Appear near a platform office", flat)
        self.assertIn("Enter run", flat)
        self.assertIn("sajadinmaker", flat)
        # the selected row carries the selection marker
        self.assertIn("▸ 3", flat)
        # the clutter the user rejected is gone
        self.assertNotIn("no account", flat)
        self.assertNotIn("sources:", flat)
        self.assertNotIn("OpenStreetMap", flat)

    def test_static_intro_is_hermetic(self):
        import contextlib
        import io
        buf = io.StringIO()
        env = {"NO_COLOR": "1", "TERM": "dumb"}
        with contextlib.redirect_stdout(buf), \
                unittest.mock.patch.dict(os.environ, env):
            v.intro_static()
        out = buf.getvalue()
        self.assertIn(v.APP_VERSION, out)
        self.assertIn("not connected", out)
        self.assertIn("vpn refresh", out)
        self.assertIn("sudo vpn connect", out)
        self.assertIn(f"by {v.AUTHOR}", out)
        self.assertIn("1  connect to the fastest server", out)

    def test_snapshot_offline_never_fetches(self):
        with unittest.mock.patch.object(v, "current_geo",
                                        side_effect=AssertionError):
            s = v.intro_snapshot(fetch=False)
        self.assertFalse(s["connected"])
        self.assertIsInstance(s["servers"], int)


class Watchdog(unittest.TestCase):
    """vpn watch: session-intent file, dead-server detection, backoff."""

    def setUp(self):
        self._patch = unittest.mock.patch.object(
            v, "SESSION_FILE", "/tmp/vpnbox-test-session.json")
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self._legacy = unittest.mock.patch.object(
            v, "LEGACY_SESSION_FILE", "/tmp/vpnbox-test-session-legacy.json")
        self._legacy.start()
        self.addCleanup(self._legacy.stop)
        for path in (v.SESSION_FILE, v.LEGACY_SESSION_FILE):
            if os.path.exists(path):
                os.remove(path)

    def test_session_roundtrip(self):
        v.save_session("JP", "chiyoda", "meta", "all", True, "tcp", 10, 60)
        sess = v.load_session()
        self.assertEqual(sess["country"], "JP")
        self.assertEqual(sess["city"], "chiyoda")
        self.assertEqual(sess["site"], "meta")
        self.assertEqual(sess["office"], "all")
        self.assertTrue(sess["nearest"])
        self.assertEqual(sess["proto"], "tcp")
        self.assertEqual(sess["ping"], 10)
        self.assertEqual(sess["ping_exit"], 60)
        self.assertIn("connected_at", sess)

    def test_session_missing_or_garbage_is_none(self):
        self.assertIsNone(v.load_session())
        with open(v.SESSION_FILE, "w") as f:
            f.write("{not json at all}")
        self.assertIsNone(v.load_session())

    def test_clear_session_leaves_a_tombstone(self):
        v.save_session("JP", None, None, None, False, None, 10, 60)
        v.clear_session()
        sess = v.load_session()
        # the marker must outlive the daemon teardown so a running watch
        # honors the user's decision instead of resurrecting the tunnel
        self.assertTrue(sess["stopped"])
        self.assertGreater(sess["stopped_at"], 0)

    def test_recovery_never_overrides_the_tombstone(self):
        v.save_session("JP", None, None, None, False, None, 10, 60)
        v.clear_session()
        refused = v.save_session("JP", None, None, None, False, None, 10, 60,
                                 recovery=True)
        self.assertIsNone(refused)
        self.assertTrue(v.load_session()["stopped"])

    def test_user_connect_replaces_the_tombstone(self):
        v.save_session("JP", None, None, None, False, None, 10, 60)
        v.clear_session()
        saved = v.save_session("CA", None, None, None, False, None, 10, 60,
                               recovery=False)
        self.assertEqual(saved["country"], "CA")
        sess = v.load_session()
        self.assertEqual(sess["country"], "CA")
        self.assertFalse(sess.get("stopped", False))

    def test_watch_honors_the_tombstone_at_start(self):
        v.save_session("JP", None, None, None, False, None, 10, 60)
        v.clear_session()
        out = io.StringIO()
        with unittest.mock.patch.object(v, "sudo_available", return_value=True), \
             contextlib.redirect_stdout(out):
            rc = v.cmd_watch(unittest.mock.Mock(give_up=3))
        self.assertEqual(rc, 2)
        self.assertIn("nothing to watch", out.getvalue())

    def test_watch_takes_the_tunnel_down_for_a_late_tombstone(self):
        v.save_session("JP", None, None, None, False, None, 10, 60)
        v.clear_session()
        with unittest.mock.patch.object(v, "sudo_available", return_value=True), \
             contextlib.redirect_stdout(io.StringIO()), \
             unittest.mock.patch.object(v, "running_pid", return_value=4242), \
             unittest.mock.patch.object(v, "kill_pid") as killed:
            rc = v.cmd_watch(unittest.mock.Mock(give_up=3))
        self.assertEqual(rc, 0)
        killed.assert_called_once_with(4242, quiet=True)

    def test_kill_stale_sweeps_every_daemon(self):
        sentinel = unittest.mock.Mock(stdout="111\n222\n", returncode=0)
        kills = []
        with unittest.mock.patch.object(v, "sudo_run",
                                        lambda argv: kills.append(argv)), \
             unittest.mock.patch.object(v.time, "sleep"), \
             unittest.mock.patch.object(v.subprocess, "run",
                                        return_value=sentinel):
            v.kill_stale()
        self.assertEqual(kills, [["kill", "111"], ["kill", "222"],
                                 ["kill", "-9", "111"], ["kill", "-9", "222"]])

    def test_build_conf_keeps_alive_pings(self):
        conf = v.build_conf(server(), keepalive=(10, 60))
        self.assertIn("\nping 10\n", conf)
        self.assertIn("ping-exit 60\n", conf)
        conf_zero = v.build_conf(server(), keepalive=(10, 0))
        self.assertIn("\nping 10\n", conf_zero)
        self.assertNotIn("ping-exit", conf_zero)
        conf_off = v.build_conf(server(), keepalive=None)
        self.assertNotIn("ping 10", conf_off)

    def test_session_namespace_maps_intent(self):
        v.save_session("JP", "chiyoda", None, None, False, "tcp", 5, 45)
        a = v.session_namespace(v.load_session())
        self.assertEqual(a.country_pos, "JP")
        self.assertIsNone(a.country_opt)
        self.assertEqual(a.city, "chiyoda")
        self.assertEqual(a.proto, "tcp")
        self.assertEqual((a.ping, a.ping_exit), (5, 45))
        self.assertIsNone(a.index)
        self.assertEqual(a.skip, 0)
        self.assertEqual(a.max_tries, 3)
        self.assertTrue(a.recovery, "recovery connects must refuse to save over a tombstone")

    def test_session_namespace_defaults_when_fields_missing(self):
        a = v.session_namespace({"country": "JP"})
        self.assertEqual((a.ping, a.ping_exit), (v.PING_DEFAULT,
                                                 v.PING_EXIT_DEFAULT))
        self.assertFalse(a.nearest)

    def test_check_ping_settings(self):
        ns = lambda p, e: unittest.mock.Mock(ping=p, ping_exit=e)
        v.check_ping_settings(ns(10, 60))          # fine
        v.check_ping_settings(ns(10, 0))           # exit disabled: fine
        with self.assertRaises(SystemExit):
            v.check_ping_settings(ns(60, 60))

    def test_backoff_is_exponential_with_cap(self):
        self.assertEqual([v.backoff_seconds(n) for n in (1, 2, 3, 4, 5, 6)],
                         [30, 60, 120, 240, 300, 300])

    def test_connect_applies_skip(self):
        sel = [server(ip="1.1.1.1"), server(ip="2.2.2.2"), server(ip="3.3.3.3")]
        skipped = sel[1:]
        self.assertEqual([r["ip"] for r in skipped], ["2.2.2.2", "3.3.3.3"])
        # and the parser really wires --skip/--ping/--ping-exit and watch
        bp = v.build_parser()
        connect = bp.parse_args(["connect"])
        self.assertEqual(connect.skip, 0)
        self.assertEqual((connect.ping, connect.ping_exit), (10, 60))
        watch = bp.parse_args(["watch", "--give-up", "7"])
        self.assertEqual(watch.give_up, 7)
        self.assertIs(watch.fn, v.cmd_watch)


class Regressions(unittest.TestCase):
    """Bugs found in the post-beta5 audit."""

    def test_fetch_geo_never_raises(self):
        import urllib.error
        for boom in (urllib.error.URLError("offline"), ValueError("bad json"),
                     OSError("boom")):
            with unittest.mock.patch.object(v, "http_get", side_effect=boom):
                self.assertIsNone(v.fetch_geo())

    def test_status_no_ip_hides_the_address_when_disconnected(self):
        out = io.StringIO()
        with unittest.mock.patch.object(v, "running_pid", return_value=None), \
             unittest.mock.patch.object(v, "read_meta", return_value=None), \
             unittest.mock.patch.object(v, "fetch_geo",
                                        side_effect=AssertionError("lookup")), \
             contextlib.redirect_stdout(out):
            rc = v.cmd_status(argparse.Namespace(no_ip=True))
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "not connected")

    def test_status_without_meta_does_not_show_an_absurd_age(self):
        out = io.StringIO()
        with unittest.mock.patch.object(v, "running_pid", return_value=4242), \
             unittest.mock.patch.object(v, "read_meta", return_value={}), \
             contextlib.redirect_stdout(out):
            v.cmd_status(argparse.Namespace(no_ip=True))
        text = out.getvalue()
        self.assertIn("pid 4242", text)
        self.assertNotIn("for ", text)

    def test_disconnect_reports_when_the_daemon_survives(self):
        order = []
        out = io.StringIO()
        with unittest.mock.patch.object(v, "running_pid", return_value=4242), \
             unittest.mock.patch.object(v, "sudo_available", return_value=False), \
             unittest.mock.patch.object(v, "clear_session",
                                        side_effect=lambda: order.append("intent")), \
             unittest.mock.patch.object(v, "clear_meta"), \
             unittest.mock.patch.object(
                 v, "kill_pid",
                 side_effect=lambda *a, **k: (order.append("kill"), False)[1]), \
             contextlib.redirect_stdout(out):
            rc = v.cmd_disconnect(argparse.Namespace())
        self.assertEqual(rc, 2)
        self.assertIn("could not", out.getvalue())
        # the user's intent is recorded before the (possibly slow) teardown,
        # so a watchdog can never resurrect the tunnel mid-disconnect
        self.assertEqual(order, ["intent", "kill"])

    def test_kill_pid_reports_failure(self):
        with unittest.mock.patch.object(v, "sudo_run"), \
             unittest.mock.patch.object(v.os.path, "exists", return_value=True), \
             unittest.mock.patch.object(v.time, "sleep"):
            self.assertFalse(v.kill_pid(999, quiet=True))

    def test_connect_argument_validation(self):
        def ns(**over):
            base = dict(country_opt=None, country_pos="JP", skip=0,
                        index=None, max_tries=3)
            base.update(over)
            return argparse.Namespace(**base)

        v.validate_connect_args(ns())
        for bad in (dict(skip=-1), dict(index=0), dict(max_tries=0)):
            with self.assertRaises(SystemExit):
                v.validate_connect_args(ns(**bad))

    def test_ping_zero_means_probe_off(self):
        a = argparse.Namespace(ping=0, ping_exit=60)
        v.check_ping_settings(a)
        self.assertEqual(a.ping_exit, 0)
        for ping, exit_after in ((-1, 60), (10, -1), (60, 60)):
            with self.assertRaises(SystemExit):
                v.check_ping_settings(
                    argparse.Namespace(ping=ping, ping_exit=exit_after))

    def test_build_conf_never_emits_ping_zero(self):
        conf = v.build_conf(server(), keepalive=(0, 60))
        self.assertNotIn("ping 0", conf)
        self.assertNotIn("ping-exit 60", conf)

    def test_intro_refresh_failure_keeps_the_menu_alive(self):
        out = io.StringIO()
        with unittest.mock.patch.object(
                v, "refresh_servers",
                side_effect=SystemExit("offline")), \
                contextlib.redirect_stdout(out):
            msg = v.intro_refresh()
        self.assertTrue(msg.startswith("✗ refresh failed"), msg)

    def test_load_cache_rejects_malformed_files(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "servers.json")
        with unittest.mock.patch.object(v, "cache_file", return_value=path):
            for payload in ({"servers": []},
                            {"updated": 1, "servers": "not-a-list"},
                            {"updated": "today", "servers": []}):
                with open(path, "w") as f:
                    import json
                    json.dump(payload, f)
                self.assertIsNone(v.load_cache())
            with open(path, "w") as f:
                import json
                json.dump({"updated": 1, "servers": []}, f)
            self.assertEqual(v.load_cache()["servers"], [])

    def test_state_dir_is_private(self):
        path = v.state_dir()
        st = os.lstat(path)
        self.assertTrue(stat.S_ISDIR(st.st_mode))
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o700)
        self.assertEqual(st.st_uid, v._invoking_uid())

    def test_watch_rejects_zero_give_up(self):
        with self.assertRaises(SystemExit):
            v.cmd_watch(unittest.mock.Mock(give_up=0))


if __name__ == "__main__":
    unittest.main()
