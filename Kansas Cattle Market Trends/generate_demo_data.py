"""
Demo Data Generator — Kansas
=============================
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

# ── Date range: weekly Sundays for the past 52 weeks ─────────────────────────
from datetime import date, timedelta

def all_sundays(weeks=52):
    """Return the Sunday date for each of the past N weeks."""
    today = date.today()
    days_back = (today.weekday() + 1) % 7
    latest_sunday = today - timedelta(days=days_back)
    return [(latest_sunday - timedelta(weeks=w)).isoformat()
            for w in range(weeks - 1, -1, -1)]

DATES = all_sundays(52)

# ── Price model: realistic seasonal trend ────────────────────────────────────
def seasonal_price(base, date_str, amplitude=0.08, noise=0.03):
    """Returns a price with seasonal sine wave + random noise."""
    d = date.fromisoformat(date_str)
    day_of_year = d.timetuple().tm_yday
    seasonal = amplitude * math.sin((day_of_year / 365.25) * 2 * math.pi - 1.0)
    noise_factor = 1 + random.gauss(0, noise)
    return round(base * (1 + seasonal) * noise_factor, 2)

# ── Feeder Cattle price model by weight bracket ─────────────────────────────
FIXED_BRACKETS = ["<400", "400-499", "500-599", "600-699", "700-799", "800-899", "900+"]

# Inverse price curve: lighter = higher $/cwt
# Kansas prices tend to run slightly lower than south TX due to proximity to
# feedlots — less transport cost premium on lighter calves
STEER_BASE_PRICES = {
    "<400":    440,
    "400-499": 405,
    "500-599": 375,
    "600-699": 348,
    "700-799": 320,
    "800-899": 298,
    "900+":    272,
}
HEIFER_DISCOUNT = 0.88   # Heifers ~12% less than steers
BULL_PREMIUM    = 0.94   # Bulls slight discount vs steers

# Head count by bracket (Kansas markets run heavier cattle on average;
# 600-700 lb range still trades the most volume)
STEER_HEAD = {
    "<400":    40,  "400-499": 160, "500-599": 310,
    "600-699": 450, "700-799": 400, "800-899": 220, "900+": 110,
}
HEIFER_HEAD = {k: int(v * 0.65) for k, v in STEER_HEAD.items()}

# Kansas individual auction markets
MARKETS = ["Dodge City", "Pratt", "Salina"]

# Each market has a slight price premium/discount vs baseline
# Dodge City is a major feedlot hub, typically commands slight premium
MARKET_PREMIUM = {
    "Dodge City": 1.01,
    "Pratt":      0.99,
    "Salina":     1.00,
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
            "head_count": total_head * len(MARKETS)
        })
    return rows

def build_replacement_trend():
    rows = []
    for d in DATES:
        base = 2100
        p = seasonal_price(base, d, amplitude=0.12, noise=0.05)
        h = random.randint(30, 150)
        rows.append({"date": d, "avg_price": p, "head_count": h})
    return rows

def build_slaughter_trend():
    rows = []
    for d in DATES:
        base = 148
        p = seasonal_price(base, d, amplitude=0.04, noise=0.02)
        h = random.randint(200, 700)
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
        "Steers": 345, "Heifers": 304, "Bulls": 325,
        "Cows": 138, "Bred Cows": 2100, "Bred Heifers": 1850, "Stock Cows": 1550,
    }
    prices = {}
    heads  = {}
    for cls in classes:
        base = class_base[cls]
        prices[cls] = [seasonal_price(base, d, noise=0.04) for d in DATES]
        heads[cls]  = [random.randint(25, 280) for _ in DATES]
    return {"dates": DATES, "classes": classes, "prices": prices, "heads": heads}

def build_market_week_prices():
    """Weekly price rows per market per commodity type."""
    COMMODITY_CONFIG = [
        ("Feeder Cattle",      345,  0.025),
        ("Slaughter Cattle",   148,  0.020),
        ("Replacement Cattle", 2100, 0.050),
    ]
    rows = []
    for d in DATES:
        for mkt, premium in MARKET_PREMIUM.items():
            for commodity, base, noise in COMMODITY_CONFIG:
                if commodity == "Feeder Cattle":
                    h = random.randint(300, 3000)
                elif commodity == "Slaughter Cattle":
                    h = random.randint(40, 500)
                else:
                    h = random.randint(10, 120)
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
            "avg_price": seasonal_price(132 * mp, latest), "avg_weight": 1300,
            "head_count": random.randint(40, 130),
        })
        rows.append({
            "date": latest, "market": mkt, "commodity": "Slaughter Cattle",
            "class": "Bulls", "weight_bracket": "Unknown", "frame": "N/A",
            "avg_price": seasonal_price(152 * mp, latest), "avg_weight": 1560,
            "head_count": random.randint(15, 50),
        })
        # Replacement
        rows.append({
            "date": latest, "market": mkt, "commodity": "Replacement Cattle",
            "class": "Bred Cows", "weight_bracket": "Unknown", "frame": "Medium and Large",
            "avg_price": seasonal_price(2100 * mp, latest, noise=0.06), "avg_weight": 1180,
            "head_count": random.randint(10, 45),
        })
    return rows

def build_bracket_by_market():
    """Per-market bracket matrices plus '_all' combined."""
    result = {}

    result["_all"] = {
        "steers":  build_weight_bracket_matrix("steers"),
        "heifers": build_weight_bracket_matrix("heifers"),
    }

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

# ── Manifest ─────────────────────────────────────────────────────────────────
def build_manifest():
    from datetime import datetime
    return {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_data_date": DATES[-1],
        "history_days": 365,
        "ks_markets": list(MARKET_PREMIUM.keys()),
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

print("\nGenerating Kansas demo data files...")
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

print("\n✅ Kansas demo data ready. Open index.html in a browser (via a local server)")
print("   to preview the dashboard, then run fetch_data.py for real data.\n")
