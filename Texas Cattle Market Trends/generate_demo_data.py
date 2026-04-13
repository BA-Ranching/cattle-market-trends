"""
Demo Data Generator
====================
Generates realistic synthetic livestock market data in the same format
as fetch_data.py. Run this once to populate the dashboard so you can
preview the site before running the real USDA data fetch.

Usage:  python generate_demo_data.py
Then:   python fetch_data.py   (overwrites with real USDA data)
"""

import json
import os
import math
import random

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── Date range: weekly Tuesdays for the past 52 weeks ────────────────────────
from datetime import date, timedelta

def all_sundays(weeks=52):
    """Return the Sunday date for each of the past N weeks."""
    today = date.today()
    # Roll back to the most recent Sunday
    days_back = (today.weekday() + 1) % 7   # Mon=0…Sun=6 → days since last Sunday
    latest_sunday = today - timedelta(days=days_back)
    return [(latest_sunday - timedelta(weeks=w)).isoformat()
            for w in range(weeks - 1, -1, -1)]   # oldest → newest

DATES = all_sundays(52)

# ── Price model: realistic seasonal trend ────────────────────────────────────
def seasonal_price(base, date_str, amplitude=0.08, noise=0.03):
    """Returns a price with seasonal sine wave + random noise."""
    d = date.fromisoformat(date_str)
    day_of_year = d.timetuple().tm_yday
    # Peak in spring (Apr) and fall (Oct), dip in summer and winter
    seasonal = amplitude * math.sin((day_of_year / 365.25) * 2 * math.pi - 1.0)
    noise_factor = 1 + random.gauss(0, noise)
    return round(base * (1 + seasonal) * noise_factor, 2)

# ── Feeder Cattle price model by weight bracket ─────────────────────────────
# Lighter calves = higher $/cwt (inverse price curve)
FIXED_BRACKETS = ["<400", "400-499", "500-599", "600-699", "700-799", "800-899", "900+"]

# Inverse price curve: lighter = higher $/cwt
STEER_BASE_PRICES = {
    "<400":    450,
    "400-499": 415,
    "500-599": 385,
    "600-699": 355,
    "700-799": 328,
    "800-899": 305,
    "900+":    278,
}
HEIFER_DISCOUNT = 0.88   # Heifers ~12% less than steers
BULL_PREMIUM    = 0.94   # Bulls slight discount vs steers

# Head count by bracket (600-700 lb range trades the highest volume)
STEER_HEAD = {
    "<400":    55,  "400-499": 200, "500-599": 340,
    "600-699": 420, "700-799": 370, "800-899": 190, "900+": 75,
}
HEIFER_HEAD = {k: int(v * 0.7) for k, v in STEER_HEAD.items()}

# All individual TX auction markets (matching MARKET_REPORTS in fetch_data.py)
MARKETS = ["San Angelo", "Dalhart", "Tulia", "Wildorado", "Giddings",
           "Fort Worth (Superior)", "Fort Worth (LiveAg)"]

# Each market gets a slight price premium/discount vs the baseline
MARKET_PREMIUM = {
    "San Angelo":            0.99,
    "Dalhart":               1.00,
    "Tulia":                 0.98,
    "Wildorado":             1.01,
    "Giddings":              0.97,
    "Fort Worth (Superior)": 1.02,
    "Fort Worth (LiveAg)":   1.01,
}

# ── Build pre-computed datasets ───────────────────────────────────────────────

def build_feeder_trend():
    rows = []
    for d in DATES:
        total_head = 0
        total_value = 0
        for bracket, base in STEER_BASE_PRICES.items():
            p = seasonal_price(base, d)
            h = STEER_HEAD[bracket] + random.randint(-20, 20)
            hp = seasonal_price(base * HEIFER_DISCOUNT, d)
            hh = HEIFER_HEAD[bracket] + random.randint(-15, 15)
            total_value += p * h + hp * hh
            total_head  += h + hh
        rows.append({
            "date": d,
            "avg_price": round(total_value / max(total_head, 1), 2),
            "head_count": total_head * 2  # both markets
        })
    return rows

def build_replacement_trend():
    rows = []
    for d in DATES:
        # Replacement cattle trade by the head, not cwt — much higher dollar values
        base = 2200
        p = seasonal_price(base, d, amplitude=0.12, noise=0.05)
        h = random.randint(40, 180)
        rows.append({"date": d, "avg_price": p, "head_count": h})
    return rows

def build_slaughter_trend():
    rows = []
    for d in DATES:
        base = 150
        p = seasonal_price(base, d, amplitude=0.04, noise=0.02)
        h = random.randint(300, 800)
        rows.append({"date": d, "avg_price": p, "head_count": h})
    return rows

def build_weight_bracket_matrix(class_type="steers"):
    if class_type == "steers":
        base_prices = STEER_BASE_PRICES
        head_counts = STEER_HEAD
    else:
        base_prices = {k: round(v * HEIFER_DISCOUNT, 2) for k, v in STEER_BASE_PRICES.items()}
        head_counts = HEIFER_HEAD

    prices = {}
    heads  = {}
    for bracket in FIXED_BRACKETS:
        base = base_prices[bracket]
        prices[bracket] = [seasonal_price(base, d, noise=0.025) for d in DATES]
        heads[bracket]  = [max(0, head_counts[bracket] + random.randint(-25, 25)) for _ in DATES]
    return {"dates": DATES, "brackets": FIXED_BRACKETS, "prices": prices, "heads": heads}

def build_class_breakdown():
    classes = ["Steers", "Heifers", "Bulls", "Cows", "Bred Cows", "Bred Heifers", "Stock Cows"]
    class_base = {
        "Steers": 350, "Heifers": 308, "Bulls": 330,
        "Cows": 140, "Bred Cows": 2200, "Bred Heifers": 1900, "Stock Cows": 1600,
    }
    prices = {}
    heads  = {}
    for cls in classes:
        base = class_base[cls]
        prices[cls] = [seasonal_price(base, d, noise=0.04) for d in DATES]
        heads[cls]  = [random.randint(30, 300) for _ in DATES]
    return {"dates": DATES, "classes": classes, "prices": prices, "heads": heads}

def build_market_week_prices():
    """Weekly price rows per market per commodity type."""
    # (commodity_name, base_price, unit)
    # Feeder/Slaughter are $/cwt; Replacement is $/head
    COMMODITY_CONFIG = [
        ("Feeder Cattle",      350,  0.025),
        ("Slaughter Cattle",   150,  0.020),
        ("Replacement Cattle", 2200, 0.050),
    ]
    rows = []
    for d in DATES:
        for mkt, premium in MARKET_PREMIUM.items():
            for commodity, base, noise in COMMODITY_CONFIG:
                # Smaller markets trade fewer replacement/slaughter cattle
                if commodity == "Feeder Cattle":
                    h = random.randint(400, 3500)
                elif commodity == "Slaughter Cattle":
                    h = random.randint(50, 600)
                else:
                    h = random.randint(10, 150)
                p = round(seasonal_price(base * premium, d, noise=noise), 2)
                rows.append({
                    "date": d, "market": mkt, "commodity": commodity,
                    "avg_price": p, "head_count": h,
                })
    return rows

BRACKET_MID = {
    "<400": 350, "400-499": 450, "500-599": 550,
    "600-699": 650, "700-799": 750, "800-899": 850, "900+": 950,
}

def build_cattle_latest():
    latest = DATES[-1]
    rows = []
    for mkt in MARKETS:
        mp = MARKET_PREMIUM[mkt]
        for bracket, base in STEER_BASE_PRICES.items():
            mid = BRACKET_MID[bracket]
            rows.append({
                "date": latest, "market": mkt, "commodity": "Feeder Cattle",
                "class": "Steers", "weight_bracket": bracket, "frame": "Medium and Large",
                "avg_price": seasonal_price(base * mp, latest),
                "avg_weight": mid + 25,
                "head_count": STEER_HEAD[bracket] + random.randint(-20, 20),
            })
            rows.append({
                "date": latest, "market": mkt, "commodity": "Feeder Cattle",
                "class": "Heifers", "weight_bracket": bracket, "frame": "Medium and Large",
                "avg_price": seasonal_price(base * HEIFER_DISCOUNT * mp, latest),
                "avg_weight": mid + 20,
                "head_count": HEIFER_HEAD[bracket] + random.randint(-10, 10),
            })
        # Slaughter cattle
        rows.append({
            "date": latest, "market": mkt, "commodity": "Slaughter Cattle",
            "class": "Cows", "weight_bracket": "Unknown", "frame": "N/A",
            "avg_price": seasonal_price(135 * mp, latest), "avg_weight": 1280,
            "head_count": random.randint(50, 150),
        })
        rows.append({
            "date": latest, "market": mkt, "commodity": "Slaughter Cattle",
            "class": "Bulls", "weight_bracket": "Unknown", "frame": "N/A",
            "avg_price": seasonal_price(155 * mp, latest), "avg_weight": 1540,
            "head_count": random.randint(20, 60),
        })
        # Replacement
        rows.append({
            "date": latest, "market": mkt, "commodity": "Replacement Cattle",
            "class": "Bred Cows", "weight_bracket": "Unknown", "frame": "Medium and Large",
            "avg_price": seasonal_price(2200 * mp, latest, noise=0.06), "avg_weight": 1150,
            "head_count": random.randint(15, 50),
        })
    return rows

def build_bracket_by_market():
    """Per-market bracket matrices plus '_all' combined, matching fetch_data.py structure."""
    result = {}

    # _all: combined across all markets (same as the standalone files)
    result["_all"] = {
        "steers":  build_weight_bracket_matrix("steers"),
        "heifers": build_weight_bracket_matrix("heifers"),
    }

    # Per-market: apply each market's price premium to simulate different price levels
    for mkt in MARKETS:
        mp = MARKET_PREMIUM[mkt]
        steer_prices  = {b: round(v * mp, 2) for b, v in STEER_BASE_PRICES.items()}
        heifer_prices = {b: round(v * HEIFER_DISCOUNT * mp, 2) for b, v in STEER_BASE_PRICES.items()}

        s_prices, s_heads, h_prices, h_heads = {}, {}, {}, {}
        for b in FIXED_BRACKETS:
            s_prices[b] = [seasonal_price(steer_prices[b],  d, noise=0.025) for d in DATES]
            s_heads[b]  = [max(0, STEER_HEAD[b]  + random.randint(-20, 20)) for _ in DATES]
            h_prices[b] = [seasonal_price(heifer_prices[b], d, noise=0.025) for d in DATES]
            h_heads[b]  = [max(0, HEIFER_HEAD[b] + random.randint(-15, 15)) for _ in DATES]

        result[mkt] = {
            "steers":  {"dates": DATES, "brackets": FIXED_BRACKETS, "prices": s_prices, "heads": s_heads},
            "heifers": {"dates": DATES, "brackets": FIXED_BRACKETS, "prices": h_prices, "heads": h_heads},
        }

    return result

def build_commodity_latest(feeder_trend, replacement_trend, slaughter_trend):
    """Pull the last data point from each trend so numbers match the trend charts exactly."""
    def last(trend):
        return trend[-1] if trend else {"avg_price": 0, "head_count": 0}
    return [
        {"commodity": "Feeder Cattle",      "avg_price": last(feeder_trend)["avg_price"],      "head_count": last(feeder_trend)["head_count"]},
        {"commodity": "Replacement Cattle", "avg_price": last(replacement_trend)["avg_price"],  "head_count": last(replacement_trend)["head_count"]},
        {"commodity": "Slaughter Cattle",   "avg_price": last(slaughter_trend)["avg_price"],    "head_count": last(slaughter_trend)["head_count"]},
    ]

def build_sheep():
    sheep_commodities = {
        "Feeder Sheep/Lambs": {"Hair Lambs": (280, 55), "Lambs": (300, 60)},
        "Slaughter Sheep/Lambs": {"Lambs": (275, 80), "Ewes": (120, 140)},
        "Slaughter Goats": {
            "Kids": (310, 65), "Nannies/Does": (140, 100),
            "Wethers": (165, 130), "Bucks/Billies": (220, 120),
        },
        "Feeder Goats": {"Kids": (350, 45), "Yearlings": (250, 75)},
    }
    rows = []
    for d in DATES:  # Weekly sheep/goat reports
        for commodity, classes in sheep_commodities.items():
            for cls, (base_price, base_weight) in classes.items():
                p = seasonal_price(base_price, d, amplitude=0.1, noise=0.04)
                h = random.randint(15, 800)
                rows.append({
                    "d": d, "c": commodity, "k": cls,
                    "p": round(p, 2),
                    "w": round(base_weight + random.gauss(0, 5), 1),
                    "h": h,
                })
    return rows

# ── Manifest ─────────────────────────────────────────────────────────────────
def build_manifest():
    from datetime import datetime
    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_data_date": DATES[-1],
        "history_days": 365,
        "tx_markets": list(MARKET_PREMIUM.keys()),
        "note": "DEMO DATA — run fetch_data.py to load real USDA market data",
    }

# ── Save all files ────────────────────────────────────────────────────────────
def save(filename, data):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    rows = len(data) if isinstance(data, list) else (len(data.get("dates", [])) if isinstance(data, dict) and "dates" in data else "—")
    size = os.path.getsize(path) / 1024
    print(f"  ✓ {filename:35s} {str(rows):>6} rows  ({size:.1f} KB)")

print("\nGenerating demo data files...")
save("manifest.json",              build_manifest())
feeder_trend      = build_feeder_trend()
replacement_trend = build_replacement_trend()
slaughter_trend   = build_slaughter_trend()
save("feeder_trend.json",          feeder_trend)
save("replacement_trend.json",     replacement_trend)
save("slaughter_trend.json",       slaughter_trend)
save("weight_bracket_steers.json",      build_weight_bracket_matrix("steers"))
save("weight_bracket_heifers.json",     build_weight_bracket_matrix("heifers"))
save("weight_bracket_by_market.json",   build_bracket_by_market())
save("class_breakdown.json",            build_class_breakdown())
save("market_week_prices.json",    build_market_week_prices())
save("cattle_latest.json",         build_cattle_latest())
save("commodity_latest.json",      build_commodity_latest(feeder_trend, replacement_trend, slaughter_trend))
save("sheep_compact.json",         build_sheep())

print("\n✅ Demo data ready. Open index.html in a browser (via a local server)")
print("   to preview the dashboard, then run fetch_data.py for real data.\n")
