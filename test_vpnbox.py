"""vpnbox unit tests — fully hermetic: no network, no root, no caches.

Run from the repo root:
    python3 -m unittest discover -s . -p "test_*.py" -v     (or: make test)
"""
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
