#!/usr/bin/env python3
"""vpnbox — a free, country/city-rich VPN manager for Linux.

Fetches the live public server list from **VPN Gate** (the open, academic
VPN relay project by the University of Tsukuba, https://vpngate.net),
enriches each server with city/ISP geolocation, and connects through it
with OpenVPN 2.6+ while keeping DNS on systemd-resolved.

All server data is fetched live and anonymously — no account, no key,
no payment. Volunteer servers rotate often; refresh points you at the
hosted ones that are alive right now.

Quick start:
  vpn refresh                      # download + parse + geolocate server list
  vpn countries                    # countries available right now
  vpn servers JP                   # servers in Japan (use 2-letter code or name)
  sudo vpn connect --country Japan --city Tokyo
  sudo vpn connect US              # best reachable US server
  sudo vpn connect                 # best reachable server anywhere
  vpn sites                        # 24 platforms, 200+ offices worldwide
  sudo vpn connect --site meta     # nearest live server to Meta HQ (Menlo Park)
  sudo vpn connect --site x        # nearest live server to X/Twitter HQ (SF)
  sudo vpn connect --site meta --office Dublin   # target a specific office
  vpn status                       # connection + exit-IP info
  vpn disconnect                   # (works with or without sudo)
  sudo vpn disconnect              # ensure privileged removal of leftovers

Attribution: server list by the VPN Gate academic experiment.
Update regularly with `vpn refresh`. Use responsibly and legally.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
import os
import pwd
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

APP = "vpnbox"
APP_VERSION = "1.0.0-beta4"
UA = f"{APP}/{APP_VERSION} (linux; free public VPN client)"
PID_FILE = "/run/vpnbox.pid"
LOG_FILE = "/var/log/vpnbox.log"
CONF_FILE = "/tmp/vpnbox-openvpn.ovpn"
META_FILE = "/var/tmp/vpnbox.meta"

DEFAULT_SOURCE = "https://www.vpngate.net/api/iphone/"
PROTO_IN_CONFIG = re.compile(r"^\s*proto\s+(\S+)", re.M)
REMOTE_IN_CONFIG = re.compile(r"^\s*remote\s+(\S+)\s+(\d+)", re.M)

# Windows-only directives that make OpenVPN on Linux error out — strip them.
STRIP_PREFIXES = (
    "win-sys", "route-method", "route-delay", "dhcp-renew", "dhcp-release",
    "show-net-up", "ip-win32", "register-dns", "tun-ipv6",
)

DNS_HELPER = "/etc/openvpn/update-systemd-resolved"

EXTRA_CONFIG = """\
### vpnbox additions (below are ours; keep them last)
script-security 2
data-ciphers AES-256-GCM:AES-128-GCM:AES-192-GCM:AES-256-CBC:AES-128-CBC:CHACHA20-POLY1305
connect-retry 2  8
connect-retry-max 3
pull-filter ignore "bypass-dhcp"
# full-tunnel enforcement — don't trust the server to push these:
redirect-gateway def1
block-ipv6
"""
if os.path.exists(DNS_HELPER):
    EXTRA_CONFIG += (
        f"up {DNS_HELPER}\n"
        f"down {DNS_HELPER}\n"
        "down-pre\n"
    )

FAIL_MARKERS = (
    "Options error", "AUTH_FAILED", "Cannot resolve host", "Connection refused",
    "Connection timed out", "Connection reset by peer", "No route to host",
    "Network is unreachable", "Error opening configuration file",
    "Failed to establish", "TUNSETIFF failed",
    "All connections have been", "Exiting due to fatal error",
)

OK_MARKER = "Initialization Sequence Completed"


# ----------------------------------------------------------------------------
# platform HQ / area shortcuts for `vpn connect --site …`
# (approx coordinates; we connect to the NEAREST live volunteer server)
# ----------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


SITES = {
    "meta": {"label": "Meta HQ (Facebook/Threads)", "offices": [
        ("US", "Menlo Park, CA (HQ)", 37.4529, -122.1817, "1601 Willow Road, Menlo Park, California"),
        ("US", "San Francisco, CA", 37.7895, -122.3959, "181 Fremont Street, San Francisco"),
        ("US", "New York, NY", 40.7355, -73.9932, "770 Broadway, New York"),
        ("US", "Seattle, WA", 47.6253, -122.3397, "1101 Dexter Avenue North, Seattle"),
        ("US", "Austin, TX", 30.2672, -97.7431, "300 West 6th Street, Austin"),
        ("US", "Chicago, IL", 41.8781, -87.6298, "641 North Wells Street, Chicago"),
        ("US", "Los Angeles, CA", 34.0522, -118.2437, ""),
        ("IE", "Dublin (EU HQ)", 53.3415, -6.2416, "Grand Canal Dock, Dublin"),
        ("GB", "London (UK)", 51.5155, -0.0975, "1 Rathbone Square, London"),
        ("FR", "Paris", 48.8566, 2.3522, ""),
        ("DE", "Berlin", 52.5200, 13.4050, ""),
        ("ES", "Madrid", 40.4168, -3.7038, ""),
        ("IT", "Milan", 45.4642, 9.1900, ""),
        ("PL", "Warsaw", 52.2297, 21.0122, ""),
        ("SE", "Stockholm", 59.3293, 18.0686, ""),
        ("NL", "Amsterdam", 52.3676, 4.9041, ""),
        ("IL", "Tel Aviv", 32.0853, 34.7818, ""),
        ("AE", "Dubai (MENA)", 25.2048, 55.2708, ""),
        ("SG", "Singapore (APAC)", 1.2806, 103.8550, "South Beach Tower, Singapore"),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("TH", "Bangkok", 13.7563, 100.5018, ""),
        ("ID", "Jakarta", -6.2088, 106.8456, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
        ("MX", "Mexico City", 19.4326, -99.1332, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("IN", "Gurgaon (Delhi NCR)", 28.4595, 77.0266, ""),
        ("IN", "Hyderabad", 17.3850, 78.4867, ""),
    ]},
    "instagram": {"label": "Instagram HQ (Meta)", "offices": [
        ("US", "Menlo Park, CA (HQ)", 37.4529, -122.1817, "1601 Willow Road, Menlo Park, California"),
        ("US", "San Francisco, CA (original HQ)", 37.7895, -122.3959, "181 Fremont Street, San Francisco"),
        ("US", "New York, NY (creator hub)", 40.7355, -73.9932, "770 Broadway, New York"),
        ("US", "Los Angeles, CA (creators)", 34.0522, -118.2437, ""),
        ("GB", "London (UK)", 51.5155, -0.0975, "1 Rathbone Square, London"),
        ("IE", "Dublin (EU)", 53.3415, -6.2416, "Grand Canal Dock, Dublin"),
        ("FR", "Paris", 48.8566, 2.3522, ""),
        ("DE", "Berlin", 52.5200, 13.4050, ""),
        ("SG", "Singapore (APAC)", 1.2806, 103.8550, "South Beach Tower, Singapore"),
        ("JP", "Tokyo", 35.6580, 139.7016, "Shibuya Stream, Tokyo"),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("TH", "Bangkok", 13.7563, 100.5018, ""),
        ("ID", "Jakarta", -6.2088, 106.8456, ""),
        ("AE", "Dubai (MENA)", 25.2048, 55.2708, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
        ("MX", "Mexico City", 19.4326, -99.1332, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("IN", "Gurgaon (Delhi NCR)", 28.4595, 77.0266, ""),
    ]},
    "threads": {"label": "Threads HQ (Meta)", "offices": [
        ("US", "Menlo Park, CA (HQ)", 37.4529, -122.1817, "1601 Willow Road, Menlo Park, California"),
        ("US", "San Francisco, CA", 37.7895, -122.3959, "181 Fremont Street, San Francisco"),
        ("GB", "London (UK)", 51.5155, -0.0975, "1 Rathbone Square, London"),
    ]},
    "x": {"label": "X / Twitter HQ", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7765, -122.4168, "1355 Market Street, San Francisco"),
        ("US", "New York, NY", 40.7417, -73.9965, ""),
        ("GB", "London (UK)", 51.5142, -0.0960, ""),
        ("JP", "Tokyo", 35.6875, 139.7450, ""),
        ("SG", "Singapore", 1.2830, 103.8513, ""),
        ("AE", "Dubai (MENA)", 25.0995, 55.1590, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
    ]},
    "whatsapp": {"label": "WhatsApp HQ (Meta)", "offices": [
        ("US", "Menlo Park, CA (HQ)", 37.4529, -122.1817, "1601 Willow Road, Menlo Park, California"),
        ("US", "San Francisco, CA", 37.7793, -122.4140, ""),
        ("GB", "London (EU office)", 51.5155, -0.0975, "1 Rathbone Square, London"),
        ("SG", "Singapore (APAC)", 1.2806, 103.8550, ""),
        ("IN", "Mumbai (India)", 19.0760, 72.8777, ""),
    ]},
    "google": {"label": "Google HQ (Alphabet)", "offices": [
        ("US", "Mountain View, CA (HQ)", 37.4220, -122.0841, "1600 Amphitheatre Parkway, Mountain View"),
        ("US", "San Francisco, CA", 37.7915, -122.3930, "345 Spear Street, San Francisco"),
        ("US", "New York, NY", 40.7415, -73.9936, "111 Eighth Avenue, New York"),
        ("US", "Seattle, WA", 47.6493, -122.3465, ""),
        ("US", "Cambridge, MA", 42.3629, -71.0923, ""),
        ("US", "Chicago, IL", 41.8855, -87.6479, ""),
        ("IE", "Dublin (EU HQ)", 53.3480, -6.2590, "Gordon House, Dublin"),
        ("GB", "London (King's Cross)", 51.5344, -0.1240, "6 Pancras Square, London"),
        ("FR", "Paris", 48.8738, 2.2950, ""),
        ("DE", "Berlin", 52.5200, 13.4050, ""),
        ("DE", "Munich", 48.1351, 11.5820, ""),
        ("CH", "Zurich", 47.3700, 8.5380, ""),
        ("ES", "Madrid", 40.4168, -3.7038, ""),
        ("PL", "Warsaw (campus)", 52.2297, 21.0122, ""),
        ("IL", "Tel Aviv", 32.0794, 34.7880, "Electra Tower, Tel Aviv"),
        ("JP", "Tokyo (Shibuya)", 35.6580, 139.7016, "Shibuya Stream, Tokyo"),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("SG", "Singapore", 1.2820, 103.8510, ""),
        ("AU", "Sydney (Pyrmont)", -33.8732, 151.1948, "48 Pirrama Road, Pyrmont"),
        ("BR", "São Paulo", -23.6100, -46.6970, ""),
        ("IN", "Bengaluru", 12.9716, 77.5946, ""),
        ("IN", "Hyderabad", 17.3850, 78.4867, ""),
        ("IN", "Gurgaon", 28.4595, 77.0266, ""),
        ("KE", "Nairobi (Africa HQ)", -1.2864, 36.8172, ""),
    ]},
    "youtube": {"label": "YouTube HQ (Google)", "offices": [
        ("US", "San Bruno, CA (HQ)", 37.6203, -122.4057, "901 Cherry Avenue, San Bruno"),
        ("US", "New York, NY", 40.7415, -73.9936, "111 Eighth Avenue, New York"),
        ("GB", "London (King's Cross)", 51.5344, -0.1240, ""),
        ("JP", "Tokyo (Roppongi)", 35.6604, 139.7290, "Roppongi Hills, Tokyo"),
        ("SG", "Singapore", 1.2820, 103.8510, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "microsoft": {"label": "Microsoft / LinkedIn", "offices": [
        ("US", "Redmond, WA (HQ)", 47.6423, -122.1271, "One Microsoft Way, Redmond"),
        ("US", "San Francisco, CA", 37.7899, -122.3902, ""),
        ("US", "New York, NY", 40.7561, -73.9872, "11 Times Square, New York"),
        ("CA", "Vancouver", 49.2827, -123.1207, ""),
        ("CA", "Toronto (Canada HQ)", 43.6532, -79.3832, ""),
        ("MX", "Mexico City", 19.4326, -99.1332, ""),
        ("GB", "London (UK)", 51.4975, -0.1416, ""),
        ("IE", "Dublin (EU HQ)", 53.3415, -6.2416, ""),
        ("NL", "Amsterdam", 52.3676, 4.9041, ""),
        ("FR", "Paris (Issy)", 48.8260, 2.2770, ""),
        ("DE", "Munich", 48.1351, 11.5820, ""),
        ("ES", "Madrid", 40.4168, -3.7038, ""),
        ("IT", "Milan", 45.4642, 9.1900, ""),
        ("SE", "Stockholm", 59.3293, 18.0686, ""),
        ("PL", "Warsaw", 52.2297, 21.0122, ""),
        ("IL", "Herzliya", 32.1624, 34.8447, ""),
        ("AE", "Dubai", 25.2048, 55.2708, ""),
        ("IN", "Bengaluru", 12.9716, 77.5946, ""),
        ("IN", "Hyderabad (Gachibowli)", 17.4400, 78.3480, ""),
        ("IN", "Gurgaon", 28.4595, 77.0266, ""),
        ("JP", "Tokyo (Shinagawa)", 35.6264, 139.7445, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("CN", "Beijing", 39.9042, 116.4074, ""),
        ("CN", "Shanghai", 31.2304, 121.4737, ""),
        ("TW", "Taipei", 25.0330, 121.5654, ""),
        ("SG", "Singapore", 1.2806, 103.8550, ""),
        ("AU", "Sydney (North Ryde)", -33.8100, 151.1800, ""),
        ("ID", "Jakarta", -6.2088, 106.8456, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "linkedin": {"label": "LinkedIn HQ", "offices": [
        ("US", "Sunnyvale, CA (HQ)", 37.3688, -122.0363, "1000 West Maude Avenue, Sunnyvale"),
        ("US", "San Francisco, CA", 37.7830, -122.3920, "222 Second Street, San Francisco"),
        ("US", "New York, NY", 40.7484, -73.9857, "Empire State Building, New York"),
        ("US", "Austin, TX", 30.2672, -97.7431, ""),
        ("CA", "Toronto", 43.6532, -79.3832, ""),
        ("IE", "Dublin (EU HQ)", 53.3350, -6.2400, ""),
        ("GB", "London (UK)", 51.5155, -0.0975, ""),
        ("AE", "Dubai (MENA)", 25.2048, 55.2708, ""),
        ("SG", "Singapore (APAC)", 1.2806, 103.8550, ""),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("IN", "Bengaluru", 12.9716, 77.5946, ""),
        ("IN", "Gurgaon", 28.4595, 77.0266, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "tiktok": {"label": "TikTok HQ (ByteDance)", "offices": [
        ("US", "Los Angeles, CA (US HQ)", 34.0983, -118.3217, "5800 Sunset Boulevard, Los Angeles"),
        ("US", "Mountain View, CA", 37.3861, -122.0839, ""),
        ("US", "New York, NY", 40.7128, -74.0060, ""),
        ("GB", "London (UK)", 51.5142, -0.0960, ""),
        ("IE", "Dublin (EU)", 53.3415, -6.2416, ""),
        ("SG", "Singapore (HQ)", 1.2966, 103.7890, ""),
        ("JP", "Tokyo (Shibuya)", 35.6580, 139.7016, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("ID", "Jakarta", -6.2088, 106.8456, ""),
        ("TH", "Bangkok", 13.7563, 100.5018, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
        ("AE", "Dubai (MENA)", 25.2048, 55.2708, ""),
    ]},
    "snapchat": {"label": "Snapchat HQ (Snap Inc.)", "offices": [
        ("US", "Santa Monica, CA (HQ)", 34.0181, -118.4513, "2772 Donald Douglas Loop North, Santa Monica"),
        ("US", "New York, NY", 40.7268, -74.0048, ""),
        ("GB", "London (UK)", 51.5155, -0.0972, ""),
        ("FR", "Paris", 48.8698, 2.3076, ""),
        ("AE", "Dubai (MENA)", 25.2048, 55.2708, ""),
        ("SG", "Singapore (APAC)", 1.2806, 103.8550, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "discord": {"label": "Discord HQ", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7699, -122.4013, "444 De Haro Street, San Francisco"),
        ("US", "New York, NY", 40.7268, -74.0048, ""),
    ]},
    "reddit": {"label": "Reddit HQ", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7910, -122.4020, ""),
        ("US", "New York, NY", 40.7128, -74.0060, ""),
        ("GB", "London (UK)", 51.5074, -0.1278, ""),
    ]},
    "pinterest": {"label": "Pinterest HQ", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7726, -122.3963, "651 Brannan Street, San Francisco"),
        ("GB", "London (UK)", 51.5074, -0.1278, ""),
        ("FR", "Paris", 48.8566, 2.3522, ""),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "apple": {"label": "Apple HQ", "offices": [
        ("US", "Cupertino, CA (Apple Park)", 37.3346, -122.0090, "Apple Park, Cupertino"),
        ("US", "Austin, TX", 30.2672, -97.7431, ""),
        ("US", "New York, NY", 40.7128, -74.0060, ""),
        ("GB", "London (Battersea)", 51.4828, -0.1460, "Battersea Power Station, London"),
        ("FR", "Paris", 48.8738, 2.2950, ""),
        ("DE", "Munich (silicon design)", 48.1351, 11.5820, ""),
        ("IL", "Herzliya", 32.1624, 34.8447, ""),
        ("CN", "Shanghai", 31.2304, 121.4737, ""),
        ("JP", "Tokyo (Marunouchi)", 35.6812, 139.7671, ""),
        ("IN", "Bengaluru", 12.9716, 77.5946, ""),
        ("SG", "Singapore", 1.2806, 103.8550, ""),
    ]},
    "telegram": {"label": "Telegram HQ", "offices": [
        ("AE", "Dubai (HQ)", 25.2048, 55.2708, ""),
        ("GB", "London (office)", 51.5074, -0.1278, ""),
        ("DE", "Berlin (dev office)", 52.5200, 13.4050, ""),
    ]},
    "signal": {"label": "Signal Foundation", "offices": [
        ("US", "San Francisco, CA", 37.7749, -122.4194, ""),
    ]},
    "tumblr": {"label": "Tumblr HQ", "offices": [
        ("US", "New York, NY", 40.7128, -74.0060, ""),
        ("CA", "Montreal (dev office)", 45.5019, -73.5674, ""),
    ]},
    "viber": {"label": "Viber HQ (Rakuten)", "offices": [
        ("CY", "Limassol (HQ)", 34.6831, 33.0935, ""),
        ("IL", "Tel Aviv", 32.0853, 34.7818, ""),
        ("BY", "Minsk (dev office)", 53.9006, 27.5590, ""),
        ("PH", "Manila (dev office)", 14.5995, 120.9842, ""),
    ]},
    "line": {"label": "LINE HQ (messaging)", "offices": [
        ("JP", "Tokyo (Yoyogi, HQ)", 35.6702, 139.6995, ""),
        ("JP", "Fukuoka", 33.5904, 130.4017, ""),
        ("TH", "Bangkok", 13.7563, 100.5018, ""),
        ("TW", "Taipei", 25.0330, 121.5654, ""),
        ("ID", "Jakarta", -6.2088, 106.8456, ""),
    ]},
    "kakaotalk": {"label": "KakaoTalk HQ", "offices": [
        ("KR", "Jeju (HQ)", 33.5000, 126.5312, ""),
        ("KR", "Pangyo (Seoul metro)", 37.4020, 127.0930, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
    ]},
    "wechat": {"label": "WeChat HQ (Tencent)", "offices": [
        ("CN", "Shenzhen (HQ)", 22.5285, 113.9345, "Tencent Binhai Towers, Shenzhen"),
        ("CN", "Guangzhou", 23.1291, 113.2644, ""),
        ("CN", "Beijing", 39.9042, 116.4074, ""),
        ("CN", "Shanghai", 31.2304, 121.4737, ""),
        ("HK", "Hong Kong", 22.3193, 114.1694, ""),
        ("SG", "Singapore (intl)", 1.3521, 103.8198, ""),
        ("US", "Palo Alto, CA", 37.4443, -122.1600, ""),
    ]},
    "netflix": {"label": "Netflix HQ (streaming)", "offices": [
        ("US", "Los Gatos, CA (HQ)", 37.3609, -121.9748, "121 Albright Way, Los Gatos"),
        ("US", "Los Angeles, CA", 34.0986, -118.3247, "Sunset Bronson Studios, Los Angeles"),
        ("US", "New York, NY", 40.7411, -73.9880, ""),
        ("NL", "Amsterdam (EMEA HQ)", 52.3676, 4.9041, ""),
        ("GB", "London (UK)", 51.5074, -0.1278, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("SG", "Singapore (APAC)", 1.3521, 103.8198, ""),
        ("KR", "Seoul", 37.5665, 126.9780, ""),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
    ]},
    "twitch": {"label": "Twitch HQ (Amazon)", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7905, -122.4029, "225 Bush Street, San Francisco"),
    ]},
    "slack": {"label": "Slack HQ (Salesforce)", "offices": [
        ("US", "San Francisco, CA (HQ)", 37.7889, -122.3969, "500 Howard Street, San Francisco"),
        ("IE", "Dublin (EU)", 53.3415, -6.2416, ""),
        ("GB", "London (UK)", 51.5142, -0.0960, ""),
        ("JP", "Tokyo", 35.6580, 139.7016, ""),
    ]},
    "zoom": {"label": "Zoom HQ", "offices": [
        ("US", "San Jose, CA (HQ)", 37.3376, -121.8919, ""),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
        ("AU", "Sydney", -33.8688, 151.2093, ""),
        ("IN", "Bengaluru", 12.9716, 77.5946, ""),
    ]},
    "quora": {"label": "Quora HQ", "offices": [
        ("US", "Mountain View, CA", 37.3861, -122.0839, ""),
    ]},
    "spotify": {"label": "Spotify HQ (audio)", "offices": [
        ("SE", "Stockholm (HQ)", 59.3392, 18.0760, "Birger Jarlsgatan 61, Stockholm"),
        ("US", "New York, NY", 40.7128, -74.0134, "World Trade Center, New York"),
        ("GB", "London (UK)", 51.5074, -0.1278, ""),
        ("DE", "Berlin", 52.5200, 13.4050, ""),
        ("FR", "Paris", 48.8566, 2.3522, ""),
        ("IT", "Milan", 45.4642, 9.1900, ""),
        ("ES", "Madrid", 40.4168, -3.7038, ""),
        ("JP", "Tokyo", 35.6762, 139.6503, ""),
        ("SG", "Singapore (APAC)", 1.3521, 103.8198, ""),
        ("IN", "Mumbai", 19.0760, 72.8777, ""),
        ("BR", "São Paulo", -23.5505, -46.6333, ""),
    ]},
    "vk": {"label": "VK HQ (Russian social)", "offices": [
        ("RU", "Moscow (HQ)", 55.7558, 37.6173, ""),
    ]},
}

SITE_ALIASES = {
    "twitter": "x", "ig": "instagram", "fb": "meta", "facebook": "meta",
    "wa": "whatsapp", "yt": "youtube", "snap": "snapchat", "kk": "kakaotalk",
    "tg": "telegram", "li": "linkedin", "pin": "pinterest", "ms": "microsoft",
    "sp": "spotify", "nflx": "netflix", "zho": "wechat",
}

# rough centroids for nearest-neighbour suggestions of countries
COUNTRY_CENTROIDS = {
    "US": (39.8283, -98.5795), "CA": (56.1304, -106.3468),
    "PH": (12.8797, 121.7740), "JP": (36.2048, 138.2529),
    "KR": (35.9078, 127.7669), "TH": (15.8700, 100.9925),
    "AU": (-25.2744, 133.7751), "RU": (61.5240, 105.3188),
    "GB": (54.0000, -2.0000), "HK": (22.3964, 114.1095),
    "MY": (4.2105, 101.9758), "SG": (1.3521, 103.8198),
    "AE": (23.4241, 53.8478), "CN": (35.8617, 104.1954),
    "IE": (53.4129, -8.2439), "DE": (51.1657, 10.4515),
    "FR": (46.6034, 2.2137), "NL": (52.1326, 5.2913),
    "BR": (-14.2350, -51.9253), "IN": (20.5937, 78.9629),
    "VN": (14.0583, 108.2772), "TW": (23.6978, 120.9605),
    "ID": (-2.5489, 118.0143), "ES": (40.4637, -3.7492),
    "IT": (41.8719, 12.5674), "SE": (60.1282, 18.6435),
    "PL": (51.9194, 19.1451), "CH": (46.8182, 8.2275),
    "MX": (23.6345, -102.5528), "NO": (60.4720, 8.4689),
    "FI": (61.9241, 25.7482), "DK": (56.2639, 9.5018),
    "AT": (47.5162, 14.5501), "CZ": (49.8175, 15.4730),
    "UA": (48.3794, 31.1656), "TR": (38.9637, 35.2432),
    "BD": (23.6850, 90.3563), "PK": (30.3753, 69.3451),
    "SA": (23.8859, 45.0792), "EG": (26.8206, 30.8025),
    "ZA": (-30.5595, 22.9375), "NG": (9.0820, 8.6753),
    "AR": (-38.4161, -63.6167), "CL": (-35.6751, -71.5430),
    "PE": (-9.1900, -75.0152), "CO": (4.5709, -74.2973),
    "NZ": (-40.9006, 174.8860),
}


# ----------------------------------------------------------------------------
# terminal helpers
# ----------------------------------------------------------------------------

def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM") not in (None, "dumb")


COLOR = _supports_color()


def paint(s: str, code: str) -> str:
    return f"\x1b[{code}m{s}\x1b[0m" if COLOR else s


def bold(s):  return paint(s, "1")
def green(s): return paint(s, "32")
def yellow(s): return paint(s, "33")
def red(s):   return paint(s, "31")
def cyan(s):  return paint(s, "36")
def dim(s):   return paint(s, "2")
def rev(s):   return paint(s, "7")   # reverse video — lazygit-style selection


def clip(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def human_speed(bps):
    try:
        bps = int(bps)
    except (TypeError, ValueError):
        return "?"
    for unit in ("bps", "Kbps", "Mbps", "Gbps"):
        if bps < 1000 or unit == "Gbps":
            return f"{bps:,.0f} {unit}" if unit == "bps" else f"{bps:.1f} {unit}"
        bps /= 1000


def quiet_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------
# paths / identities
# ----------------------------------------------------------------------------

def real_home() -> str:
    """Home of the actual invoking user, even under `sudo vpn ...`."""
    su = os.environ.get("SUDO_USER")
    if su and os.geteuid() == 0:
        try:
            return pwd.getpwnam(su).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


def cache_file() -> str:
    return os.path.join(real_home(), ".cache", "vpnbox", "servers.json")


def load_cache():
    path = cache_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "servers" not in data:
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(data):
    path = cache_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    # if we ran under sudo, hand the file back to the invoking user
    su = os.environ.get("SUDO_USER")
    if su and os.geteuid() == 0:
        try:
            u = pwd.getpwnam(su)
            os.chown(path, u.pw_uid, u.pw_gid)
        except (KeyError, OSError):
            pass


# ----------------------------------------------------------------------------
# server list: fetch, parse, geolocate
# ----------------------------------------------------------------------------

def source_urls() -> list:
    urls = []
    if os.environ.get("VPNGATE_API"):
        urls.append(os.environ["VPNGATE_API"])
    urls += [DEFAULT_SOURCE, "http://www.vpngate.net/api/iphone/"]
    return urls


def http_get(url, timeout=45, data=None, headers=None):
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": UA, **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_list_text() -> str:
    last_err = None
    for url in source_urls():
        try:
            text = http_get(url).decode("utf-8", "replace")
            if "#HostName" in text:
                return text
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise SystemExit(f"{APP}: could not fetch the VPN Gate list ({last_err}). "
                     f"Try again later or set VPNGATE_API to a mirror URL.")


def parse_list(text: str) -> list:
    header = None
    body = []
    for line in text.splitlines():
        if line.startswith("*") :          # softether framing markers
            continue
        if header is None:
            if line.startswith("#HostName"):
                header = line.lstrip("#").split(",")
            continue
        if line.startswith("#") or not line.strip():
            continue
        body.append(line.rstrip("\r"))
    if header is None:
        raise SystemExit(f"{APP}: unrecognized VPN Gate response format.")

    hmap = {name.strip().lower(): i for i, name in enumerate(header)}
    idx = {k: hmap.get(k) for k in (
        "hostname", "ip", "score", "ping", "speed",
        "countrylong", "countryshort", "numvpnsessions", "uptime",
        "logtype", "operator", "openvpn_configdata_base64",
    )}
    missing = [k for k, i in idx.items() if i is None]
    if missing:
        raise SystemExit(f"{APP}: VPN Gate API columns missing: {missing}")

    servers = []
    for row in csv.reader(io.StringIO("\n".join(body))):
        try:
            if len(row) < len(header) - 2:
                continue
            b64 = row[idx["openvpn_configdata_base64"]].strip()
            if len(b64) < 200:
                continue  # no usable OpenVPN profile
            cfg = base64.b64decode(b64).decode("utf-8", "replace")
            proto = "udp"
            port = ""
            m = PROTO_IN_CONFIG.search(cfg)
            if m:
                proto = m.group(1).replace("tcp-client", "tcp")
            m = REMOTE_IN_CONFIG.search(cfg)
            if m:
                port = m.group(2)
            servers.append({
                "host":  row[idx["hostname"]].strip(),
                "ip":    row[idx["ip"]].strip(),
                "score": quiet_int(row[idx["score"]]),
                "ping":  quiet_int(row[idx["ping"]]),
                "speed": quiet_int(row[idx["speed"]]),
                "country":  row[idx["countrylong"]].strip(),
                "cc":       row[idx["countryshort"]].strip().upper(),
                "sessions": quiet_int(row[idx["numvpnsessions"]]),
                "uptime":   quiet_int(row[idx["uptime"]]),
                "log":      row[idx["logtype"]].strip(),
                "operator": row[idx["operator"]].strip(),
                "proto":    proto,
                "port":     port,
                "cfg":      cfg,
                "city": "", "isp": "",        # filled by enrich_city()
                "region": "", "lat": None, "lon": None,
            })
        except Exception:
            continue
    return servers


def rank(r):
    # valid pings first; UDP preferred (volunteer TCP relays drop more),
    # then throughput, then ping, then vpn-gate score
    ok = 0 if 0 < r["ping"] < 900 else 1
    udp = 0 if r.get("proto") == "udp" else 1
    return (ok, udp, -r["speed"],
            r["ping"] if r["ping"] > 0 else 10**9, -r["score"])


def fetch_geo():
    j = json.loads(http_get(
        "http://ip-api.com/json?fields=status,country,countryCode,"
        "regionName,city,isp,query", timeout=8))
    return j if isinstance(j, dict) and j.get("status") == "success" else None


def enrich_city(servers, top=300):
    """ip-api.com free batch geolocation (100 IPs/req, best-effort)."""
    targets = sorted(servers, key=lambda r: -r["score"])[:top]
    ips = [r["ip"] for r in targets]
    ok = 0
    for c in range(0, len(ips), 100):
        chunk = ips[c:c + 100]
        try:
            payload = json.dumps(chunk).encode()
            resp = http_get(
                "http://ip-api.com/batch?fields=status,country,countryCode,"
                "regionName,city,isp,lat,lon,query", timeout=20,
                data=payload, headers={"Content-Type": "application/json"})
            rows = json.loads(resp)
            by_ip = {str(r.get("query")): r for r in rows if isinstance(r, dict)}
            for r in targets:
                g = by_ip.get(r["ip"])
                if g and g.get("status") == "success":
                    r["city"] = g.get("city") or ""
                    r["isp"]  = g.get("isp") or ""
                    r["region"] = g.get("regionName") or ""
                    r["lat"] = g.get("lat")
                    r["lon"] = g.get("lon")
                    if r["city"]:
                        ok += 1
        except Exception:
            continue
    return ok


# ----------------------------------------------------------------------------
# openvpn configuration + process control
# ----------------------------------------------------------------------------

def build_conf(r, with_dns=True) -> str:
    lines = [
        l for l in r["cfg"].splitlines()
        if l.strip() and not l.strip().lower().startswith(STRIP_PREFIXES)
    ]
    extra = EXTRA_CONFIG if with_dns else EXTRA_CONFIG
    header = (f"### vpnbox profile — server {r['host']} ({r['country']})\n"
              f"### ip={r['ip']} city={r['city'] or '?'} isp={r['isp'] or '?'}\n"
              f"### generated {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return header + "\n".join(lines) + "\n" + extra


def running_pid():
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace")
    except OSError:
        return None
    return pid if CONF_FILE in cmd else None


def sudo_available() -> bool:
    try:
        return subprocess.run(["sudo", "-n", "true"],
                              capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def sudo_run(argv):
    if os.geteuid() == 0:
        return subprocess.run(argv)
    return subprocess.run(["sudo", "-n"] + argv)


def launch(r):
    conf = build_conf(r)
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        f.write(conf)
    try:
        os.chmod(CONF_FILE, 0o600)
    except OSError:
        pass
    # Remember where the shared log ends NOW — wait_ready() must only match
    # markers in bytes THIS session appends. Without this, a stale OK line
    # from a previous session makes us report success for a dead server.
    try:
        start_off = os.path.getsize(LOG_FILE)
    except OSError:
        start_off = 0
    argv = ["openvpn", "--config", CONF_FILE, "--daemon", APP,
            "--writepid", PID_FILE, "--log-append", LOG_FILE, "--verb", "3"]
    proc = sudo_run(argv)
    if proc.returncode != 0:
        return False, (red("need sudo credentials — run: sudo vpn connect ...")
                       if not os.geteuid() == 0 else
                       red("openvpn failed to start (check your privileges)"))
    return True, start_off


def wait_ready(seconds=24, start_off=0):
    """Watch ONLY the log bytes this session appends (offset-tracked).

    The daemon log is append-shared across sessions; a stale OK line from a
    previous session must never be treated as this session's handshake.
    """
    start = time.time()

    def tail_from(offset, limit=14000):
        try:
            with open(LOG_FILE, "r", errors="replace") as f:
                f.seek(max(0, offset))
                return f.read(limit)
        except PermissionError:
            if os.geteuid() == 0:
                return ""
            # log is root-owned 0600; read the session window via sudo
            r = subprocess.run(
                ["sudo", "-n", "tail", "-c", f"+{max(1, offset + 1)}", LOG_FILE],
                capture_output=True, text=True, errors="replace")
            return (r.stdout or "")[:limit]
        except OSError:
            return ""

    while time.time() - start < seconds:
        pid = running_pid()
        tail = tail_from(start_off)
        if OK_MARKER in tail:
            time.sleep(1.5)   # let routes/DNS settle before trusting the tunnel
            return True, tail
        for marker in FAIL_MARKERS:
            if marker in tail:
                return False, tail
        if pid is None:
            return False, tail_from(start_off)
        time.sleep(0.75)
    return False, tail_from(start_off, 4000)


def fail_excerpt(tail, want=4):
    lines = [l for l in tail.splitlines()
             if any(w.lower() in l.lower()
                    for w in ("error", "failed", "refused", "timeout",
                              "cannot", "auth", "fatal"))]
    return lines[-want:] if lines else tail.splitlines()[-want:]


def save_meta(r):
    meta = {"host": r["host"], "ip": r["ip"], "cc": r["cc"],
            "country": r["country"], "city": r["city"], "isp": r["isp"],
            "proto": r["proto"], "port": r["port"], "started": time.time()}
    try:
        with open(META_FILE, "w") as f:
            json.dump(meta, f)
        os.chmod(META_FILE, 0o644)
    except OSError:
        pass


def read_meta():
    try:
        with open(META_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def clear_meta():
    if os.geteuid() == 0 or os.access(META_FILE, os.W_OK):
        try:
            os.remove(META_FILE)
            return
        except OSError:
            pass
    subprocess.run(["sudo", "-n", "rm", "-f", META_FILE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------

def resolve_site(name):
    key = (name or "").strip().lower()
    key = SITE_ALIASES.get(key, key)
    return key, SITES.get(key)


def refresh_servers(enrich=True):
    t0 = time.time()
    print(cyan("fetching VPN Gate public server list …"))
    text = fetch_list_text()
    servers = parse_list(text)
    if not servers:
        raise SystemExit(f"{APP}: parsed zero usable servers — API format changed?")
    print(f"parsed {bold(str(len(servers)))} servers "
          f"in {time.time() - t0:.1f}s")
    if enrich:
        print(cyan("geolocating top servers for city data … (free ip-api.com)"))
        hits = enrich_city(servers)
        print(f"  city data resolved for {bold(str(hits))} servers")
    save_cache({"updated": time.time(), "servers": servers})
    return servers


NOMINATIM = "https://nominatim.openstreetmap.org/search"


def offices_cache_file():
    return os.path.join(real_home(), ".cache", "vpnbox", "offices.json")


def load_office_cache():
    try:
        with open(offices_cache_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_office_cache(data):
    path = offices_cache_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    su = os.environ.get("SUDO_USER")
    if su and os.geteuid() == 0:
        try:
            u = pwd.getpwnam(su)
            os.chown(path, u.pw_uid, u.pw_gid)
        except (KeyError, OSError):
            pass


def geocode_offices(site_key=None, only_missing=True, quiet=False):
    """Precision upgrade: geocode office addresses via OpenStreetMap
    Nominatim (respecting their 1 req/s policy). Results are cached
    forever; built-in city-level coordinates are the fallback."""
    rec = load_office_cache()
    todo = []
    sites = SITES.items() if site_key is None else [(site_key, SITES[site_key])]
    for name, s in sites:
        od = rec.setdefault(name, {})
        for cc, place, la, lo, query in s["offices"]:
            if only_missing and place in od:
                continue
            q = query or re.sub(r"\s*\(.*?\)\s*", " ", place).strip()
            todo.append((name, place, q))
    n = len(todo)
    if n == 0:
        if not quiet:
            print(green("all office coordinates already precise (cached)"))
        return 0
    if not quiet:
        print(cyan(f"geocoding {n} offices via OpenStreetMap "
                   "(~1/s, first time only) …"))
    done = 0
    for i, (name, place, q) in enumerate(todo, 1):
        try:
            url = (f"{NOMINATIM}?q={urllib.parse.quote(q)}&format=json&limit=1"
                   "&addressdetails=0")
            rows = json.loads(http_get(
                url, timeout=20,
                headers={"User-Agent": f"{APP}/{APP_VERSION} (office geocoding)"}))
            if rows:
                rec[name][place] = {"lat": float(rows[0]["lat"]),
                                    "lon": float(rows[0]["lon"]),
                                    "src": "osm"}
                done += 1
        except Exception:
            pass  # keep built-in city-level coordinates
        if i % 10 == 0 and not quiet:
            print(f"  {i}/{n} …")
        time.sleep(1.05)  # Nominatim usage policy
    save_office_cache(rec)
    if not quiet:
        print(green(f"geocoded {done}/{n} offices (rest use city-level fallback)"))
    return done


def offices_distance(offices, r, rec=None, site_key=None):
    """km distance from a server to the nearest of the given offices,
    using OSM-geocoded coordinates when available."""
    if r.get("lat") is None or r.get("lon") is None:
        return None
    site_rec = (rec or {}).get(site_key, {}) if site_key else {}
    best = None
    for cc, place, la, lo, q in offices:
        hit = site_rec.get(place)
        if hit:
            la, lo = hit["lat"], hit["lon"]
        d = haversine_km(r["lat"], r["lon"], la, lo)
        if best is None or d < best:
            best = d
    return best


def dist_tier(d):
    """Rank accuracy tiers: inside a tier, ping/speed decides — so a slightly
    closer-but-dead server never beats a fast one you can actually use."""
    if d <= 40:   return 0
    if d <= 150:  return 1
    if d <= 500:  return 2
    if d <= 1500: return 3
    return 4


def site_candidates(servers, offices, country=None, city=None,
                    rec=None, site_key=None):
    out = servers
    if country:
        q = country.strip()
        c1 = [r for r in out if r["cc"] == q.upper()]
        if not c1:
            c1 = [r for r in out if q.lower() in r["country"].lower()]
        out = c1
    if city:
        out = [r for r in out
               if city.lower() in f"{r['city']} {r['isp']} {r['host']}".lower()]

    def key(r):
        d = offices_distance(offices, r, rec, site_key)
        if d is None:
            return (9, rank(r))
        return (dist_tier(d), rank(r))

    return sorted(out, key=key), ""


def cmd_refresh(args):
    servers = refresh_servers(enrich=not args.no_cities)
    ping_ok = [r for r in servers if 0 < r["ping"] < 900]
    countries = len({r["cc"] for r in servers})
    print(green("done: ") + f"{len(servers)} servers, {countries} countries, "
          f"{len(ping_ok)} responsive now. cached at {cache_file()}")
    by_cc = {}
    for r in servers:
        by_cc[r["cc"]] = by_cc.get(r["cc"], 0) + 1
    top = sorted(by_cc.items(), key=lambda kv: -kv[1])[:12]
    print("top countries: " + ", ".join(f"{c} {n}" for c, n in top))


def cmd_countries(args):
    cache = load_cache()
    if not cache:
        raise SystemExit("no server list yet — run: vpn refresh")
    countries = {}
    for r in cache["servers"]:
        c = countries.setdefault(r["cc"], {"name": r["country"], "n": 0,
                                           "sess": 0, "ping": []})
        c["n"] += 1
        c["sess"] += r["sessions"]
        if 0 < r["ping"] < 900:
            c["ping"].append(r["ping"])
    rows = sorted(countries.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    shown = rows if args.all else rows[:40]
    header = f"{'code':<5} {'country':<27}{'servers':>9}{'sessions':>11}{'ping':>12}"
    print(bold(header))
    print("-" * 64)
    for cc, c in shown:
        ping = f"{min(c['ping'])} ms" if c["ping"] else "—"
        print(f"{cc:<5} {clip(c['name'], 27):<27} {c['n']:>9} {c['sess']:>11} {ping:>12}")
    if not args.all and len(rows) > 40:
        print(f"… {len(rows) - 40} more, use  vpn countries --all")


def cmd_servers(args):
    cache = load_cache()
    if not cache:
        raise SystemExit("no server list yet — run: vpn refresh")
    sel, why = select_servers(cache["servers"], args.code, None)
    if args.city:
        sel, why = select_servers(sel, args.code, args.city)
    if not sel:
        raise SystemExit(f"{APP}: no match for {args.code!r}" + why)
    ages = " (list updated %s)" % time.strftime("%Y-%m-%d %H:%M", time.localtime(cache["updated"]))
    print(f"{len(sel)} servers {ages}")
    head = (f"{'#':>3} {'ip':<16}{'city':<20}{'ping':>8}{'speed':>12}"
            f"  {'proto/port':<10}{'sessions':>9}  host")
    print(bold(head)); print("-" * 100)
    for i, r in enumerate(sel[: args.limit], 1):
        p = f"{r['ping']} ms" if 0 < r["ping"] < 900 else "—"
        print(f"{i:>3} {r['ip']:<16}{clip(r['city'] or '—', 19):<20}{p:>8}"
              f"{human_speed(r['speed']):>12}  {r['proto']}/{r['port'] or '?':<10}"
              f"{r['sessions']:>9}  {clip(r['host'], 26)}")


def select_servers(servers, country=None, city=None):
    why = []
    out = servers
    if country:
        q = country.strip()
        out = [r for r in out if r["cc"] == q.upper()]
        if not out:
            out = [r for r in servers if q.lower() in r["country"].lower()]
            if not out:
                return [], f"country {q!r} not found"
    if city:
        tmp = [r for r in out if city.lower() in (f"{r['city']} {r['isp']} {r['host']}".lower())]
        if not tmp:
            cities = sorted({r["city"] for r in out if r["city"]})
            avail = ", ".join(cities[:12]) or "(no city data — refresh again)"
            why.append(f"city ?{city}? not found for {country}; known: {avail}")
            tmp = []
        else:
            out = tmp
    out = sorted(out, key=rank)
    return out, "".join(why)


def cmd_connect(args):
    args.country = args.country_opt or args.country_pos
    cache = load_cache()
    if not cache:
        raise SystemExit("no server list yet — run: vpn refresh")

    old = running_pid()
    if old:
        print(yellow(f"existing connection (pid {old}) found — replacing it"))
        kill_pid(old)

    # auto-refresh when the cache is missing or >30 min old (the volunteer
    # pool churns; new PH/US/CA etc. servers appear all the time)
    if not cache or time.time() - cache["updated"] > 1800:
        print(yellow("server list missing or >30 min old — refreshing first …"))
        try:
            refresh_servers(enrich=True)
            cache = load_cache()
        except SystemExit:
            if not cache:
                raise
            print(yellow("refresh failed — falling back to the cached list"))

    site = offices = office_name = rec = key = None
    if args.site:
        key, site = resolve_site(args.site)
        if not site:
            raise SystemExit("unknown site " + repr(args.site) +
                             "; known sites: " + ", ".join(sorted(SITES)) +
                             "  (see: vpn sites)")
        offices = site["offices"]
        if args.office:
            oq = args.office.strip().lower()
            if oq in ("all", "any", "worldwide"):
                office_name = "any office (worldwide)"
            else:
                m = [o for o in site["offices"]
                     if oq in o[1].lower() or oq == o[0].lower()]
                if not m:
                    raise SystemExit(
                        "no office matches " + repr(args.office) + " in " +
                        key + "; offices: " +
                        "; ".join(p for _c, p, *_x in site["offices"]))
                offices = m
                office_name = (m[0][1] if len(m) == 1 else
                               f"{len(m)} offices matching {args.office!r}")
        else:
            office_name = site["offices"][0][1] + " (primary HQ)"
        # precision pass: OSM-geocode the offices we're actually using
        # (first time only, cached forever after)
        try:
            geocode_offices(key, only_missing=True, quiet=True)
        except Exception:
            pass
        rec = load_office_cache()
        print(bold(f"site: {site['label']}") + f"  target: {office_name}")

    if args.site:
        sel, why = site_candidates(cache["servers"], offices,
                                   args.country, args.city, rec, key)
    else:
        sel, why = select_servers(cache["servers"], args.country, args.city)
    if args.proto:
        sel = [r for r in sel if r["proto"] == args.proto]
    if args.index:
        if 1 <= args.index <= len(sel):
            sel = sel[args.index - 1: args.index]
        else:
            raise SystemExit(f"--index out of range (list has {len(sel)})")
    if not sel and not args.site and args.country:
        # graceful nearest-neighbour offer when a country has zero live servers
        cent = COUNTRY_CENTROIDS.get(args.country.strip().upper())
        if cent:
            geo = [r for r in cache["servers"] if r["lat"] is not None]
            geo.sort(key=lambda r: haversine_km(r["lat"], r["lon"], cent[0], cent[1]))
            if geo:
                r0 = geo[0]
                d0 = haversine_km(r0["lat"], r0["lon"], cent[0], cent[1])
                print(yellow(f"no live servers in {args.country} right now. "
                             f"closest pool: {r0['cc']} — "
                             f"{r0['city'] or r0['host']} ({d0:.0f} km away)"))
                if args.nearest:
                    sel = geo
                    print(cyan("--nearest: connecting through the closest "
                               "available servers instead"))
                else:
                    raise SystemExit(
                        f"{APP}: stopped — rerun with --nearest to go via "
                        f"{r0['cc']} ({r0['city'] or r0['host']})")
    if not sel:
        raise SystemExit(f"{APP}: no candidates. {why or 'try another country/city'}")

    if os.geteuid() != 0 and not sudo_available():
        print(red("I do not have sudo privileges right now."))
        hint = f"sudo vpn connect {args.country or ''}".strip()
        print(f"run it as:  " + bold(f"{hint} {('--city ' + args.city) if args.city else ''}".strip()))
        return 2

    tries = sel[: args.max_tries]
    for i, r in enumerate(tries, 1):
        loc = f"{r['country']} / {r['city'] or r['host']} ({r['ip']})"
        site_note = ""
        if site:
            d = offices_distance(offices, r, rec, key)
            if d is not None:
                site_note = f"   [{office_name}: {d:.0f} km]"
        print(f"\nattempt {i}/{len(tries)}: {bold(loc)}  "
              f"[{r['proto']}/{r['port'] or '?'} ping {r['ping']}ms]{site_note}")
        ok, started = launch(r)
        if not ok:
            print(red(f"  could not start openvpn: {started}"))
            continue
        print("  launching openvpn (with DNS handling) …")
        ready, tail = wait_ready(start_off=started)
        if ready:
            save_meta(r)
            info = fetch_geo()
            print("")
            print(green(bold("CONNECTED")) + f"  via {r['host']}  [{r['country']}"
                  + (f" → {r['city']}" if r["city"] else "") + "]")
            if site:
                d = offices_distance(offices, r, rec, key)
                if d is not None:
                    print(f"  site    : {site['label']} — {office_name} · "
                          f"{d:.0f} km from target")
            if info:
                print(f"  exit IP : {info.get('query')}")
                print(f"  location: {info.get('country')}, "
                      f"{info.get('city') or info.get('regionName') or '?'}  "
                      f"(isp {info.get('isp')})")
                if r["cc"] and str(info.get("countryCode", "")).upper() != r["cc"].upper():
                    print(red("  WARNING: exit-IP country differs from the selected "
                              "server — full-tunnel routing may not be active. "
                              "Check with: vpn status"))
            print("  run 'vpn status' anytime; disconnect with " +
                  bold("vpn disconnect"))
            return 0
        # clean the failed attempt
        pid = running_pid()
        if pid:
            kill_pid(pid, quiet=True)
        for line in fail_excerpt(tail):
            print(red("  × " + clip(line, 110)))
        time.sleep(1)
    print(yellow("all attempts failed. volunteer servers are dynamic — "
                 "VPN Gate entries may vanish. try: ") +
          bold("vpn refresh") + yellow(" or another country"))
    raise SystemExit(1)


def kill_pid(pid, quiet=False):
    argv = ["kill", str(pid)]
    sudo_run(argv)
    for _ in range(24):
        if not os.path.exists(f"/proc/{pid}"):
            break
        time.sleep(0.25)
    if os.path.exists(f"/proc/{pid}"):
        sudo_run(["kill", "-9", str(pid)])
        time.sleep(0.5)
    if not quiet:
        print(green("openvpn stopped"))
    # remove root-owned leftovers
    sudo_run(["rm", "-f", PID_FILE, CONF_FILE, META_FILE])


def cmd_disconnect(args):
    pid = running_pid()
    if os.geteuid() != 0 and not sudo_available() and pid is None:
        meta = read_meta()
        if not meta:
            print("not connected"); return 0
        print(red("needs sudo to check/remove root daemon state")); return 2
    if pid:
        print(f"terminating openvpn (pid {pid}) …")
        kill_pid(pid)
        clear_meta()
    else:
        clear_meta()
        # also clean forgotten files
        if os.geteuid() != 0 and sudo_available():
            subprocess.run(["sudo", "-n", "rm", "-f", PID_FILE, CONF_FILE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("not connected (cleaned any leftovers)")


def cmd_status(args):
    pid = running_pid()
    if not pid:
        print(bold("not connected"))
        meta = read_meta()
        if meta:
            try: clear_meta()
            except Exception: pass
        local = fetch_geo()
        if local:
            print(f"your current (unprotected) IP: {local.get('query')} — "
                  f"{local.get('country')}, {local.get('city') or '?'}")
        return 0
    meta = read_meta() or {}
    age = int(time.time() - meta.get("started", 0))
    age_s = f"{age // 3600}h{(age % 3600) // 60}m" if age >= 3600 else (
        f"{age // 60}m{age % 60}s")
    print(green(bold("connected")) + f"   pid {pid}   for {age_s}")
    print(f"  server  : {meta.get('host')}  {meta.get('ip')} "
          f"{meta.get('proto')}/{meta.get('port') or '?'}")
    print(f"  country : {meta.get('country')}" +
          (f" → {meta.get('city')}" if meta.get("city") else ""))
    if meta.get("isp"):
        print(f"  isp     : {meta.get('isp')}")
    if not args.no_ip:
        info = fetch_geo()
        if info:
            print(f"  exit IP : {info.get('query')}   "
                  f"{info.get('country')}, {info.get('city') or '?'} "
                  f"(isp {info.get('isp')})")
            if meta.get("cc") and info.get("countryCode", "").upper() != meta["cc"]:
                print(yellow("  note: exit IP country differs from selected server — "
                             "openvpn fallback may be active"))

def cmd_ip(args):
    info = fetch_geo()
    if info:
        for k in ("query", "country", "regionName", "city", "isp"):
            print(f"  {k:<10} : {info.get(k, '')}")
    else:
        print(red("geolocation lookup failed"))


def cmd_sites(args):
    cache = load_cache()
    servers = cache["servers"] if cache else []
    if args.recache:
        geocode_offices(None, only_missing=False)
        print(green("office geocache rebuilt"))
        return
    if args.site:
        key, site = resolve_site(args.site)
        if not site:
            raise SystemExit("unknown site " + repr(args.site) +
                             "; known: " + ", ".join(sorted(SITES)))
        if args.geocode:
            geocode_offices(key, only_missing=True)
        rec = load_office_cache().get(key, {})
        total_offices = sum(len(s["offices"]) for s in SITES.values())
        print(bold(site["label"]) +
              f"  ·  {len(site['offices'])} of {total_offices} offices "
              "worldwide in the database")
        for cc, place, la, lo, q in site["offices"]:
            hit = rec.get(place)
            ela, elo, src = ((hit["lat"], hit["lon"], "osm") if hit
                             else (la, lo, "city-level"))
            cand = [r for r in servers if r["lat"] is not None]
            if cand:
                best = min(cand, key=lambda r: haversine_km(r["lat"], r["lon"], ela, elo))
                d = haversine_km(best["lat"], best["lon"], ela, elo)
                near = (f"nearest server: {clip(best['city'] or best['host'], 20)} "
                        f"({best['cc']}), {d:,.0f} km, ping {best['ping']} ms, "
                        f"speed {human_speed(best['speed'])}")
            else:
                near = "no cached servers — run: vpn refresh"
            mark = "◈" if src == "osm" else "·"
            print(f" {mark} {clip(place, 30):<30} [{cc}]  {near}")
        print("  ◈ = OSM-precise · connect: " +
              bold(f"sudo vpn connect --site {key} [--office CITY]") +
              "  (--office all = worldwide)")
        return
    if not servers:
        print("no cached server list yet — run: vpn refresh, then re-check sites")
        return
    total_offices = sum(len(s["offices"]) for s in SITES.values())
    print(bold(f"platform HQ / area shortcuts — {total_offices} offices, "
               f"{len(SITES)} platforms") +
          "  ·  'vpn connect --site NAME [--office CITY]'")
    print(f"{'site':<12}{'label':<36}primary office")
    print("-" * 80)
    for name in sorted(SITES):
        s = SITES[name]
        cc, place = s["offices"][0][0], s["offices"][0][1]
        print(f"{name:<12}{clip(s['label'], 35):<36}"
              f"{clip(place, 24)} [{cc}] +{len(s['offices']) - 1}")


# ----------------------------------------------------------------------------
# parser
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# interactive intro — bare `vpn` / `vpn intro`; pure ANSI + stdlib, no curses
# ----------------------------------------------------------------------------

BANNER = """\
 _    __      ____       _   __      ____      ____      _  __
| |  / /     / __ \\     / | / /     / __ )    / __ \\    | |\\ /
| | / /     / /_/ /    /  |/ /     / __  |   / / / /    |   /
| |\\ /     / ____/    / /|  /     / /_/ /   / /_/ /    /   |
|___/     /_/        /_/ |_/     /_____/    \\____/    /_/|_|""".strip("\n")

# ordered most-common-first (lazygit/k9s pattern: numeric keys jump straight
# to an action from anywhere on the screen; letters stay as secret aliases)
INTRO_ACTIONS = [
    ("fastest",    "Connect to the fastest server",
     lambda: intro_wizard("1")),
    ("country",    "Choose a country or city",
     lambda: intro_wizard("2")),
    ("office",     "Appear near a platform office (Instagram, X, YouTube…)",
     lambda: intro_wizard("3")),
    ("refresh",    "Refresh the live server list",
     lambda: intro_refresh()),
    ("disconnect", "Disconnect",
     lambda: intro_disconnect()),
    ("quit",       "Quit",
     None),
]

INTRO_KEYS = {"c": 0, "s": 2, "r": 3, "d": 4, "q": 5}   # letter aliases


def strip_ansi(s):
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def tty_width(default=90):
    try:
        cols = os.get_terminal_size(sys.stdout.fileno()).columns
        return cols if cols >= 20 else default
    except (OSError, ValueError, AttributeError):
        return default


def fit_center(line, width=None):
    if width is None:
        width = tty_width()
    vis = len(strip_ansi(line))
    return " " * max(0, (width - vis) // 2) + line


def ansi_ok():
    """true only when a full-screen UI makes sense: real TTY + colors allowed."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") in ("", "dumb"):
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def read_key():
    """one keypress → letter/number (lower), 'enter', 'up', 'down', 'esc'.

    Terminal raw mode is always restored before returning (sudo prompts and
    KeyboardInterrupt inside the UI therefore behave normally)."""
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == "\x1b":
        if select.select([sys.stdin], [], [], 0.05)[0]:
            try:
                seq = sys.stdin.read(2)
            except OSError:
                seq = ""
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "esc"
        return "esc"
    if ch in ("\r", "\n"):
        return "enter"
    if ch == "\x03":          # Ctrl-C arrives as a plain char in raw mode
        return "q"
    return ch.lower()


_GEO_MEMO = {"t": 0.0, "g": None}


def current_geo(ttl=30):
    """current-route geolocation, memoized so keypresses never block the UI."""
    now = time.time()
    if now - _GEO_MEMO["t"] > ttl:
        try:
            _GEO_MEMO["g"] = fetch_geo()
        except Exception:
            _GEO_MEMO["g"] = None
        _GEO_MEMO["t"] = now
    return _GEO_MEMO["g"]


def intro_snapshot(fetch=True):
    s = {"connected": bool(running_pid()), "servers": 0, "countries": 0,
         "age": None, "ip": None, "city": "", "country": ""}
    cache = load_cache()
    if cache:
        servers = cache.get("servers") or []
        s["servers"] = len(servers)
        s["countries"] = len({r["cc"] for r in servers})
        s["age"] = max(0, round(time.time() - cache.get("updated", 0)))
    if fetch:
        g = current_geo()
        if g:
            s["ip"] = g.get("query")
            s["city"] = g.get("city") or ""
            s["country"] = g.get("country") or ""
    return s


def _boxed(rows):
    w = max((len(strip_ansi(r)) for r in rows), default=0)
    box = [cyan("┌" + "─" * (w + 2) + "┐")]
    for r in rows:
        box.append(cyan("│ ") + r + " " * (w - len(strip_ansi(r))) + cyan(" │"))
    box.append(cyan("└" + "─" * (w + 2) + "┘"))
    return box


def intro_action_rows(sel):
    rows = []
    for i, (_aid, desc, _fn) in enumerate(INTRO_ACTIONS):
        row = f"{'▸' if i == sel else ' '} {i + 1}  {desc}"
        rows.append(rev(row) if i == sel else row)
    pad = max(len(strip_ansi(r)) for r in rows)
    return [r + " " * (pad - len(strip_ansi(r))) for r in rows]


def intro_render(s, msg="", sel=0):
    w = max(64, min(tty_width(), 100))
    out = [fit_center(cyan(line), w) for line in BANNER.splitlines()]
    out.append(fit_center(bold(f"{APP} {APP_VERSION}") +
                          " — free public VPN · no account · no key", w))
    out.append(fit_center("sources: VPN Gate · OpenStreetMap · ip-api", w))
    out.append(fit_center(dim("by sajad — github.com/sajadinmaker"), w))
    out.append("")
    # status line (btop style: header panel, human words, no jargon)
    state = green("● connected") if s["connected"] else red("○ not connected")
    where = "unknown — no internet?"
    if s["ip"]:
        extra = ", ".join(x for x in (s["city"], s["country"]) if x)
        where = s["ip"] + (f"  ·  {extra}" if extra else "")
    label = "exit IP" if s["connected"] else "your IP"
    if s["servers"]:
        if s["age"] < 15:
            age = "just now"
        elif s["age"] < 3600:
            age = f"{s['age']} s ago"
        else:
            age = f"{s['age'] // 60} min ago"
        line2 = (f"{s['servers']} live servers · {s['countries']} countries · "
                 f"list refreshed {age}")
    else:
        line2 = "no server list yet — pick 4 below to refresh"
    out += [fit_center(l, w) for l in _boxed([f"{state}   {label}: {where}",
                                              line2])]
    out.append("")
    out += [fit_center(r, w) for r in intro_action_rows(sel)]
    if msg:
        tone = yellow
        if msg.startswith("✓"):
            tone = green
        elif msg.startswith(("✗", "!")):
            tone = red
        out += ["", fit_center(tone(msg), w)]
    out.append("")
    out.append(fit_center(dim("↑/↓ select · 1–6 quick · Enter run · q quit"), w))
    return "\n".join(out)


def intro_static():
    """non-TTY path (pipes, CI): banner + status + numbered menu, exit 0."""
    for line in BANNER.splitlines():
        print(line)
    print(f"{APP} {APP_VERSION} — free public VPN for Linux "
          "(VPN Gate · OpenStreetMap · ip-api)")
    print("by sajad — github.com/sajadinmaker")
    s = intro_snapshot(fetch=False)
    state = "● connected" if s["connected"] else "○ not connected"
    if s["servers"]:
        stats = f"{s['servers']} live servers · {s['countries']} countries"
    else:
        stats = "no server list yet"
    print(f"{state}  ·  {stats}")
    print()
    print("menu — the number does the same thing once you run `vpn` in a "
          "real terminal:")
    print(" 1  connect to the fastest server   →  sudo vpn connect")
    print(" 2  choose a country or city        →  sudo vpn connect JP")
    print(" 3  appear near a platform office   →  sudo vpn connect "
          "--site instagram --office Tokyo")
    print(" 4  refresh the live server list    →  vpn refresh")
    print(" 5  disconnect                      →  sudo vpn disconnect")
    print()
    print("more: vpn status · vpn ip · vpn countries · vpn sites · vpn --help")


def run_in_ui(argv):
    """run a (possibly sudo) command with live output; return its exit code.

    The cursor is restored so sudo password prompts render normally."""
    print("\x1b[?25h", end="", flush=True)
    print()
    try:
        rc = subprocess.run(argv).returncode
    except KeyboardInterrupt:
        rc = 130
    _GEO_MEMO["t"] = 0.0            # the exit route may just have changed
    return rc


def _ask(prompt, default=""):
    try:
        a = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return a or default


def _pick_site():
    sites = sorted(SITES)
    total = sum(len(s["offices"]) for s in SITES.values())
    print()
    print(bold("Appear near which platform?") + dim(f"  ({total} offices worldwide)"))
    for i, name in enumerate(sites, 1):
        print(f"  {i:2})  {clip(name, 14):<14}  {clip(SITES[name]['label'], 42)}")
    pick = _ask("\nnumber or name, Enter = back: ")
    if pick in (None, ""):
        return None
    if pick.isdigit() and 1 <= int(pick) <= len(sites):
        return sites[int(pick) - 1]
    key, site = resolve_site(pick)
    return key if site else None


def _pick_office(key, servers):
    offices = SITES[key]["offices"]
    rec = load_office_cache().get(key, {})
    seated = [r for r in servers if r.get("lat") is not None]
    print()
    print(bold(f"{SITES[key]['label']} — {len(offices)} offices"))
    for i, (cc, place, la, lo, q) in enumerate(offices, 1):
        near = ""
        hit = rec.get(place)
        if seated:
            ela, elo = (hit["lat"], hit["lon"]) if hit else (la, lo)
            b = min(seated, key=lambda r: haversine_km(r["lat"], r["lon"], ela, elo))
            d = haversine_km(b["lat"], b["lon"], ela, elo)
            near = f"{d:,.0f} km · {clip(b['city'] or b['host'], 20)} ({b['cc']})"
        star = "◈" if hit else " "
        print(f" {i:2}{star} {clip(place, 32):<32} {near}")
    pick = _ask("\nnumber, 'all', or Enter for HQ: ")
    if pick is None:
        return None
    if pick.lower() == "all":
        return ["--office", "all"]
    if pick == "" or pick.lower() == "hq":
        return []
    if pick.isdigit() and 1 <= int(pick) <= len(offices):
        return ["--office", offices[int(pick) - 1][1]]
    return ["--office", pick]


def _connect_via(argv):
    print()
    print(dim("$ " + " ".join(argv)))
    rc = run_in_ui(argv)
    if rc == 0:
        return "✓ connected — the panel now shows where you appear from"
    return f"✗ exit code {rc} — try again, or pick another server"


def intro_wizard(preset):
    """preset: '1' fastest anywhere · '2' country/city · '3' near an office."""
    cache = load_cache()
    servers = (cache or {}).get("servers") or []
    if not servers:
        return "✗ the server list is empty — pick 4 first to refresh it"
    print("\x1b[H\x1b[2J", end="", flush=True)
    if preset == "3":
        key = _pick_site()
        if not key:
            return "! cancelled — back to the menu"
        tail = _pick_office(key, servers)
        if tail is None:
            return "! cancelled — back to the menu"
        return _connect_via(["sudo", "vpn", "connect", "--site", key] + tail)
    if preset == "2":
        counts, names = {}, {}
        for r in servers:
            counts[r["cc"]] = counts.get(r["cc"], 0) + 1
            names[r["cc"]] = r["country"]
        print()
        print(bold("Which country?"))
        for i, (cc, n) in enumerate(
                sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])), 1):
            print(f"  {i:2})  {cc:<5} {clip(names[cc], 34):<34} "
                  f"{n} live servers")
            if i >= 30:
                print("       … more — just type any country code or name")
                break
        cc = _ask("\ncode, name, or number, Enter = back: ")
        if cc in (None, ""):
            return "! cancelled — back to the menu"
        chosen = cc if cc in counts else (
            cc.upper() if cc.upper() in counts else cc)
        city = _ask("city? optional, matching anywhere (Enter to skip): ")
        if city is None:
            return "! cancelled — back to the menu"
        argv = ["sudo", "vpn", "connect", "--country", chosen]
        if city:
            argv += ["--city", city]
        return _connect_via(argv)
    return _connect_via(["sudo", "vpn", "connect"])


def intro_refresh():
    print("\x1b[?25h\x1b[H\x1b[2J", end="", flush=True)
    print(bold("Refreshing the live server list…") +
          dim("  VPN Gate is a volunteer network — up to ~20 s."))
    servers = refresh_servers(enrich=True)
    ping_ok = sum(1 for r in servers if 0 < r["ping"] < 900)
    _GEO_MEMO["t"] = 0.0
    return (f"✓ refreshed · {len(servers)} servers · "
            f"{len({r['cc'] for r in servers})} countries · "
            f"{ping_ok} responsive right now")


def intro_disconnect():
    rc = run_in_ui(["sudo", "vpn", "disconnect"])
    return ("✓ disconnected — you are back on your real connection"
            if rc == 0 else f"✗ exit code {rc}")


def intro_run(idx):
    """execute menu row idx; None means the loop should quit."""
    aid, _desc, fn = INTRO_ACTIONS[idx]
    if aid == "quit":
        return None
    return fn()


def cmd_intro(args):
    if not ansi_ok():
        intro_static()
        return 0
    sel, msg = 0, ""
    print("\x1b[?25l", end="", flush=True)          # hide cursor
    try:
        while True:
            s = intro_snapshot()
            print("\x1b[H\x1b[2J" + intro_render(s, msg, sel), flush=True)
            msg = ""
            try:
                key = read_key()
            except KeyboardInterrupt:
                break
            if key in ("esc", "q"):
                break
            elif key == "up":
                sel = (sel - 1) % len(INTRO_ACTIONS)
            elif key == "down":
                sel = (sel + 1) % len(INTRO_ACTIONS)
            elif key == "enter":
                msg = intro_run(sel)
                if msg is None:
                    break
            elif key in ("1", "2", "3", "4", "5", "6"):
                sel = int(key) - 1
                msg = intro_run(sel)
                if msg is None:
                    break
            elif key in INTRO_KEYS:
                sel = INTRO_KEYS[key]
                msg = intro_run(sel)
                if msg is None:
                    break
    finally:
        print("\x1b[?25h", end="")                # cursor back
        print()
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        prog=APP,
        description=("Manage a free, no-account VPN over public VPN Gate servers. "
                     "Server data: academic VPN Gate project (vpngate.net)."),
        epilog=("Bare 'vpn' opens the interactive screen. Connect/disconnect "
                "need root: run them with 'sudo vpn'. "
                "Countries and city lists refresh live with 'vpn refresh'."),
    )
    ap.add_argument("--version", action="version",
                    version=f"{APP} {APP_VERSION} (beta)")
    sub = ap.add_subparsers(dest="cmd", required=False)

    p = sub.add_parser("refresh", help="download + parse + geolocate the server list")
    p.add_argument("--no-cities", action="store_true",
                   help="skip the city geolocation enrichment")
    p.set_defaults(fn=cmd_refresh)

    p = sub.add_parser("countries", help="list available countries")
    p.add_argument("--all", action="store_true", help="don't truncate to 40 rows")
    p.set_defaults(fn=cmd_countries)

    p = sub.add_parser("servers", help="list servers of one country")
    p.add_argument("code", help="country code (JP) or name (Japan)")
    p.add_argument("--city", help="narrow to one city")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(fn=cmd_servers)

    p = sub.add_parser("sites", help="platform HQ / area shortcuts and "
                                     "their nearest live servers")
    p.add_argument("--site", help="show ALL worldwide offices of one site")
    p.add_argument("--geocode", action="store_true",
                   help="precisely geocode this site's offices via "
                        "OpenStreetMap first (1 req/s, cached)")
    p.add_argument("--recache", action="store_true",
                   help="re-geocode ALL sites' offices (~1/s — takes minutes)")
    p.set_defaults(fn=cmd_sites)

    p = sub.add_parser("connect", help="connect (needs sudo)")
    p.add_argument("country_pos", nargs="?", metavar="country",
                   help="country code or name as positional, e.g. 'vpn connect JP'")
    p.add_argument("--country", dest="country_opt",
                   help="country code or name as flag, e.g. --country Japan")
    p.add_argument("--city", help="match a city (substring)")
    p.add_argument("--site", help="aim near a platform HQ/area: meta, x, whatsapp, "
                                  "tiktok, youtube, telegram, line, …  (see: vpn sites)")
    p.add_argument("--office", help="target a specific office of the site "
                                    "(substring, e.g. --office Dublin; "
                                    "'all' = nearest to any office worldwide)")
    p.add_argument("--nearest", action="store_true",
                   help="when the requested country has no live servers, "
                        "connect via the nearest pool instead")
    p.add_argument("--index", type=int, help="use the Nth server shown by 'vpn servers'")
    p.add_argument("--proto", choices=("udp", "tcp"), help="prefer udp or tcp transports")
    p.add_argument("--skip", type=int, default=0, help="skip the first N candidates")
    p.add_argument("--max-tries", type=int, default=3)
    p.set_defaults(fn=cmd_connect)

    p = sub.add_parser("disconnect", help="disconnect (needs sudo if daemon root-owned)")
    p.set_defaults(fn=cmd_disconnect)

    p = sub.add_parser("status", help="show connection state and exit IP")
    p.add_argument("--no-ip", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("ip", help="show where your traffic appears from right now")
    p.set_defaults(fn=cmd_ip)

    p = sub.add_parser("intro", help="open the interactive screen "
                                     "(this is the default when run bare)")
    p.set_defaults(fn=cmd_intro)

    return ap


def main():
    args = build_parser().parse_args()
    if args.cmd is None:
        args.fn = cmd_intro          # bare `vpn` → the intro session
    try:
        rc = args.fn(args) or 0
    except KeyboardInterrupt:
        print()
        rc = 130
    except urllib.error.URLError as e:
        print(red(f"network error: {e}"))
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
