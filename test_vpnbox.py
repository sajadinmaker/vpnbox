"""vpnbox unit tests — fully hermetic: no network, no root, no caches.

Run from the repo root:
    python3 -m unittest discover -s . -p "test_*.py" -v     (or: make test)
"""
import inspect
import os
import sys
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
        # no ASCII banner, no taglines — a letterspaced bold-red title only
        self.assertNotIn("▁", v.TITLE)
        self.assertNotIn("#", v.TITLE)
        self.assertEqual("".join(v.TITLE.split()), "VPNBOX")

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
        for width in (70, 100, 200):
            bar = v.intro_titlebar(width)
            self.assertIn("V", v.strip_ansi(bar))
            # a roomy bar (48+ visible chars) — reads as a bold name strip
            self.assertGreaterEqual(len(v.strip_ansi(bar)), 46)
            # never wider than the terminal
            self.assertLessEqual(len(v.strip_ansi(bar)), width - 10)

    def test_render_fits_any_terminal_width(self):
        import re
        for width in (64, 80, 110, 160):
            with unittest.mock.patch.object(v, "tty_width", return_value=width):
                text = v.intro_render(self.FAKE_SNAP, sel=0)
            vis = max(len(l) for l in text.splitlines())
            self.assertLessEqual(vis, width,
                                 f"line overflows a {width}-col terminal")

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
        self.assertIn("by sajad", out)
        self.assertIn("1  connect to the fastest server", out)

    def test_snapshot_offline_never_fetches(self):
        with unittest.mock.patch.object(v, "current_geo",
                                        side_effect=AssertionError):
            s = v.intro_snapshot(fetch=False)
        self.assertFalse(s["connected"])
        self.assertIsInstance(s["servers"], int)


if __name__ == "__main__":
    unittest.main()
