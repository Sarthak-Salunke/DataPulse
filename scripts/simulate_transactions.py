"""
Transaction Simulator — sends realistic fake transactions to the ingest endpoint.

Usage:
    # Against local backend (default)
    python scripts/simulate_transactions.py

    # Against production backend
    python scripts/simulate_transactions.py --url https://your-backend.onrender.com

    # Control speed (default: 1 transaction every 2 seconds)
    python scripts/simulate_transactions.py --interval 0.5

    # Run for a fixed number of transactions then stop
    python scripts/simulate_transactions.py --count 50
"""

import argparse
import random
import time
import requests

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_URL      = "http://localhost:8000"
DEFAULT_INTERVAL = 2.0   # seconds between transactions
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "datapulse2024"

# ── Realistic data pools ──────────────────────────────────────────────────────

MERCHANTS = [
    # Normal — low risk
    ("Walmart Supercenter",       "grocery_pos",    10,  200),
    ("Starbucks",                 "food_dining",     3,   30),
    ("Shell Gas Station",         "gas_transport",  20,  100),
    ("Netflix",                   "entertainment",   8,   20),
    ("Amazon",                    "shopping_net",   15,  300),
    ("Uber",                      "gas_transport",   5,   60),
    ("Target",                    "shopping_pos",   10,  250),
    ("CVS Pharmacy",              "health_fitness",  5,  120),
    ("Home Depot",                "home",           20,  500),
    ("Spotify",                   "entertainment",   5,   15),
    # Suspicious — higher amounts, riskier categories
    ("International Wire Service","misc_net",      500, 4000),
    ("Luxury Watch Store",        "shopping_net",  800, 5000),
    ("Crypto Exchange",           "misc_net",      300, 8000),
    ("Electronics Megastore",     "shopping_pos",  400, 3000),
    ("Online Casino",             "entertainment", 200, 2000),
]

CARD_NUMBERS = [
    "4111111111111111",
    "5500005555555559",
    "4012888888881881",
    "378282246310005",
    "6011111111111117",
    "3056930009020004",
    "3530111333300000",
]

LOCATIONS = [
    (40.7128,  -74.0060,   0.5),    # New York
    (34.0522, -118.2437,   0.4),    # Los Angeles
    (41.8781,  -87.6298,   0.3),    # Chicago
    (29.7604,  -95.3698,   0.6),    # Houston
    (33.4484, -112.0740,   0.2),    # Phoenix
    (51.5074,   -0.1278, 150.0),    # London (high distance = suspicious)
    (48.8566,    2.3522, 200.0),    # Paris  (high distance = suspicious)
]

# ── Session ───────────────────────────────────────────────────────────────────

def login(base_url: str, username: str, password: str) -> requests.Session:
    session = requests.Session()
    resp = session.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    print(f"  Logged in as {username}")
    return session


# ── Simulator ─────────────────────────────────────────────────────────────────

def make_transaction() -> dict:
    merchant_name, category, amt_min, amt_max = random.choice(MERCHANTS)
    lat, lon, distance = random.choice(LOCATIONS)
    amt = round(random.uniform(amt_min, amt_max), 2)
    return {
        "cc_num":     random.choice(CARD_NUMBERS),
        "merchant":   merchant_name,
        "category":   category,
        "amt":        amt,
        "merch_lat":  lat + random.uniform(-0.5, 0.5),
        "merch_long": lon + random.uniform(-0.5, 0.5),
        "distance":   distance,
        "age":        random.randint(18, 75),
        "channel":    random.choice(["web", "pos", "mobile"]),
    }


def run(base_url: str, interval: float, count: int | None, username: str, password: str):
    print(f"\n  DataPulse Transaction Simulator")
    print(f"  Target : {base_url}")
    print(f"  Speed  : 1 transaction every {interval}s")
    print(f"  Count  : {'unlimited' if count is None else count}")
    print(f"  Ctrl+C to stop\n")

    session = login(base_url, username, password)

    sent = 0
    while count is None or sent < count:
        tx = make_transaction()
        try:
            resp = session.post(
                f"{base_url}/api/transactions/ingest",
                json=tx,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            decision = data.get("decision", "?")
            confidence = data.get("confidence", 0)
            flag = "🚨 FRAUD   " if decision == "FRAUD" else "✅ APPROVED"
            print(
                f"  {flag}  {tx['merchant']:<30}  "
                f"${tx['amt']:>8.2f}  "
                f"conf={confidence:>5.1f}%"
            )
        except requests.HTTPError as e:
            print(f"  ❌ HTTP {e.response.status_code}: {e.response.text[:80]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        sent += 1
        time.sleep(interval)

    print(f"\n  Done — sent {sent} transactions.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DataPulse transaction simulator")
    parser.add_argument("--url",      default=DEFAULT_URL,      help="Backend base URL")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, type=float, help="Seconds between transactions")
    parser.add_argument("--count",    default=None,             type=int,   help="Stop after N transactions (default: run forever)")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="API username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="API password")
    args = parser.parse_args()

    try:
        run(args.url, args.interval, args.count, args.username, args.password)
    except KeyboardInterrupt:
        print("\n\n  Stopped.")
