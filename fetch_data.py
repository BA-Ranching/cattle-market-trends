"""
USDA Market News Data Fetcher
==============================
Fetches Texas livestock market data from the USDA MARS API and saves
pre-computed JSON files for the dashboard website.

Run manually:  python fetch_data.py
Run via CI:    Called automatically by .github/workflows/fetch-data.yml

Requires:  pip install requests
"""

import json, os, requests, base64
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ────────────────────────────────────────────────────────────

API_BASE = "https://marsapi.ams.usda.gov/services/v1.2/reports"
API_KEY  = os.environ.get("USDA_API_KEY", "wnVdWbLAbO9voivdr3ZW1ipfe6JX/Xy3")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

AUTH_HEADER = {
    "Authorization": "Basic " + base64.b64encode((API_KEY + ":").encode()).decode()
}

# ── Report ID split ──────────────────────────────────────────────────────────
# SUMMARY_REPORTS: statewide rollups — used for overall trend charts only.
# Do NOT use for market comparison (they collapse individual auction data).
SUMMARY_REPORTS = {
    "1955": "Texas Weekly Cattle Auction Summary",
    "2710": "Texas Direct Cattle Report",
}

# MARKET_REPORTS: individual auction sites — used for market comparison charts.
# The short names here become the market labels in the dashboard.
MARKET_REPORTS = {
    "2015": "San Angelo",           # Producers Livestock Cattle - San Angelo
    "2014": "San Angelo",           # Producers Livestock Sheep & Goat - San Angelo
    "1953": "Dalhart",              # Cattlemen's Livestock Auction - Dalhart
    "1954": "Tulia",                # Tulia Livestock Auction
    "3365": "Wildorado",            # Lonestar Stockyards - Wildorado
    "3724": "Giddings",             # Giddings Livestock Auction
    "2713": "Fort Worth (Superior)",# Superior Livestock - Fort Worth
    "3892": "Fort Worth (LiveAg)",  # LiveAg Auction - Fort Worth
}

# Sheep & Goat market reports (individual)
SHEEP_MARKET_REPORTS = {
    "2014": "San Angelo",           # Producers Livestock Sheep & Goat - San Angelo
}

HISTORY_DAYS = 365
TOP_BRACKETS = 8   # Number of weight brackets to include in charts

# ── API Fetch ────────────────────────────────────────────────────────────────

def fetch_report(slug_id, start_date, end_date):
    date_filter = f"report_begin_date={start_date}:{end_date}"
    url = f"{API_BASE}/{slug_id}?allSections=true&q={date_filter}"
    print(f"  Fetching {slug_id}…", end="", flush=True)
    try:
        resp = requests.get(url, headers=AUTH_HEADER, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        rows = data[0]["results"] if data and "results" in data[0] else []
        print(f" {len(rows):,} rows")
        return rows
    except Exception as e:
        print(f" ERROR: {e}")
        return []

def fetch_report_tagged(slug_id, auction_name, start_date, end_date):
    """Fetch a market report and tag every row with the auction's short name."""
    rows = fetch_report(slug_id, start_date, end_date)
    for r in rows:
        r["_auction_name"] = auction_name
    return rows

# ── Helpers ──────────────────────────────────────────────────────────────────

def sf(v):
    try: return float(v) if v is not None else None
    except: return None

def si(v):
    try: return int(v) if v is not None else None
    except: return None

def parse_date(s):
    if not s: return None
    try: return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
    except: return s

def week_start_sunday(date_str):
    """Return the Sunday that starts the week containing date_str (YYYY-MM-DD)."""
    if not date_str: return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        # weekday(): Mon=0 … Sat=5, Sun=6  →  days back to Sunday:
        days_back = (d.weekday() + 1) % 7
        return (d - timedelta(days=days_back)).strftime("%Y-%m-%d")
    except:
        return date_str

def avg(values):
    v = [x for x in values if x is not None]
    return round(sum(v)/len(v), 2) if v else None

# ── Processing ────────────────────────────────────────────────────────────────

def process_cattle(rows):
    """Group cattle rows into (date, market, commodity, class, weight_bracket).

    Market label priority:
      1. _auction_name  — set by fetch_report_tagged() for individual market reports
      2. market_location_name — populated in some USDA report types
      3. office_name — fallback (may collapse multiple auctions in same USDA office)
    """
    groups = defaultdict(lambda: {"prices":[], "weights":[], "head":0})
    for r in rows:
        price = sf(r.get("avg_price"))
        if price is None: continue
        wl, wh = sf(r.get("weight_break_low")), sf(r.get("weight_break_high"))
        bracket = f"{int(wl)}-{int(wh)}" if wl and wh else f"{int(wl)}+" if wl else "Unknown"
        # Prefer the explicit auction tag, then location name, then office name
        market = (r.get("_auction_name")
                  or r.get("market_location_name")
                  or r.get("office_name", "Unknown"))
        key = (parse_date(r.get("report_begin_date")), market,
               r.get("commodity",""), r.get("class",""), bracket)
        groups[key]["prices"].append(price)
        w = sf(r.get("avg_weight"))
        if w: groups[key]["weights"].append(w)
        groups[key]["head"] += si(r.get("head_count")) or 0
    result = []
    for (date,market,commodity,cls,bracket),v in groups.items():
        if not v["prices"]: continue
        result.append({"date":date,"market":market,"commodity":commodity,"class":cls,
                        "weight_bracket":bracket,
                        "avg_price":round(sum(v["prices"])/len(v["prices"]),2),
                        "avg_weight":round(sum(v["weights"])/len(v["weights"]),1) if v["weights"] else None,
                        "head_count":v["head"]})
    return sorted(result, key=lambda x: x["date"] or "")

def process_sheep(rows):
    """Group sheep/goat rows."""
    groups = defaultdict(lambda: {"prices":[], "weights":[], "head":0})
    for r in rows:
        price = sf(r.get("avg_price"))
        if price is None: continue
        key = (parse_date(r.get("report_begin_date")), r.get("commodity",""), r.get("class",""))
        groups[key]["prices"].append(price)
        w = sf(r.get("avg_weight"))
        if w: groups[key]["weights"].append(w)
        groups[key]["head"] += si(r.get("head_count")) or 0
    result = []
    for (date,commodity,cls),v in groups.items():
        result.append({"d":date,"c":commodity,"k":cls,
                        "p":round(sum(v["prices"])/len(v["prices"]),2),
                        "w":round(sum(v["weights"])/len(v["weights"]),1) if v["weights"] else None,
                        "h":v["head"]})
    return sorted(result, key=lambda x: x["d"] or "")

# ── Pre-computed Dataset Builders ─────────────────────────────────────────────

def build_trend(cattle, commodity):
    """Aggregate into true Sunday-start weeks."""
    by_week = defaultdict(lambda: {"prices": [], "head": 0})
    for r in cattle:
        if commodity and r["commodity"] != commodity: continue
        w = week_start_sunday(r["date"])
        if not w: continue
        by_week[w]["prices"].append(r["avg_price"])
        by_week[w]["head"] += r["head_count"] or 0
    return sorted(
        [{"date": w, "avg_price": round(sum(v["prices"]) / len(v["prices"]), 2), "head_count": v["head"]}
         for w, v in by_week.items()],
        key=lambda x: x["date"]
    )

def build_market_week_prices(cattle):
    """Weekly (Sunday-start) avg price per market per commodity type."""
    by_key = defaultdict(lambda: {"prices": [], "head": 0})
    for r in cattle:
        w = week_start_sunday(r["date"])
        if not w: continue
        key = (w, r["market"], r["commodity"])
        by_key[key]["prices"].append(r["avg_price"])
        by_key[key]["head"] += r["head_count"] or 0
    return sorted(
        [{"date": k[0], "market": k[1], "commodity": k[2],
          "avg_price": round(sum(v["prices"]) / len(v["prices"]), 2),
          "head_count": v["head"]}
         for k, v in by_key.items()],
        key=lambda x: x["date"]
    )

def build_bracket_matrix(cattle, cls_filter, top_n=TOP_BRACKETS):
    """Weekly (Sunday-start) price matrix by weight bracket."""
    rows = [r for r in cattle
            if r["commodity"] == "Feeder Cattle"
            and r["class"] == cls_filter
            and r["weight_bracket"] != "Unknown"]
    # Find top N brackets by total head count
    bracket_head = defaultdict(int)
    for r in rows:
        bracket_head[r["weight_bracket"]] += r["head_count"] or 0
    top_brackets = sorted(bracket_head, key=lambda b: -bracket_head[b])[:top_n]
    top_brackets.sort(key=lambda b: int(b.split("-")[0]) if "-" in b else 9999)

    # Aggregate by week
    by_week_bracket = defaultdict(lambda: defaultdict(lambda: {"prices": [], "head": 0}))
    for r in rows:
        w = week_start_sunday(r["date"])
        if not w: continue
        by_week_bracket[w][r["weight_bracket"]]["prices"].append(r["avg_price"])
        by_week_bracket[w][r["weight_bracket"]]["head"] += r["head_count"] or 0

    weeks = sorted(by_week_bracket.keys())
    prices, heads = {}, {}
    for b in top_brackets:
        prices[b] = [round(sum(by_week_bracket[w][b]["prices"]) / len(by_week_bracket[w][b]["prices"]), 2)
                     if by_week_bracket[w][b]["prices"] else None for w in weeks]
        heads[b]  = [by_week_bracket[w][b]["head"] for w in weeks]
    return {"dates": weeks, "brackets": top_brackets, "prices": prices, "heads": heads}

def build_class_matrix(cattle):
    """Weekly (Sunday-start) price matrix by cattle class."""
    feeder  = [r for r in cattle if r["commodity"] == "Feeder Cattle"]
    classes = sorted(set(r["class"] for r in feeder if r["class"]))

    by_week_class = defaultdict(lambda: defaultdict(lambda: {"prices": [], "head": 0}))
    for r in feeder:
        w = week_start_sunday(r["date"])
        if not w or not r["class"]: continue
        by_week_class[w][r["class"]]["prices"].append(r["avg_price"])
        by_week_class[w][r["class"]]["head"] += r["head_count"] or 0

    weeks = sorted(by_week_class.keys())
    prices, heads = {}, {}
    for c in classes:
        prices[c] = [round(sum(by_week_class[w][c]["prices"]) / len(by_week_class[w][c]["prices"]), 2)
                     if by_week_class[w][c]["prices"] else None for w in weeks]
        heads[c]  = [by_week_class[w][c]["head"] for w in weeks]
    return {"dates": weeks, "classes": classes, "prices": prices, "heads": heads}

def build_commodity_latest(feeder_trend, replacement_trend, slaughter_trend):
    """Pull the last data point from each trend so the bar chart matches the trend lines exactly."""
    def last(trend):
        return trend[-1] if trend else {"avg_price": 0, "head_count": 0}
    return [
        {"commodity": "Feeder Cattle",      "avg_price": last(feeder_trend)["avg_price"],     "head_count": last(feeder_trend)["head_count"]},
        {"commodity": "Replacement Cattle", "avg_price": last(replacement_trend)["avg_price"], "head_count": last(replacement_trend)["head_count"]},
        {"commodity": "Slaughter Cattle",   "avg_price": last(slaughter_trend)["avg_price"],   "head_count": last(slaughter_trend)["head_count"]},
    ]

def cattle_latest_week(cattle):
    """Return all rows from the most recent Sunday-start week."""
    if not cattle: return []
    last_week = max(week_start_sunday(r["date"]) for r in cattle if r["date"])
    return [r for r in cattle if week_start_sunday(r["date"]) == last_week]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=HISTORY_DAYS)
    start_s  = start_dt.strftime("%m/%d/%Y")
    end_s    = end_dt.strftime("%m/%d/%Y")

    print(f"\nFetching USDA Texas Livestock Data  ({start_s} → {end_s})\n")

    # ── Summary reports: statewide rollups for overall trend charts ──────────
    print("── Summary (statewide trends) ──")
    summary_rows = []
    for slug_id, name in SUMMARY_REPORTS.items():
        # Only fetch cattle summary (1955); skip direct report (2710) unless needed
        if "Sheep" not in name and "Goat" not in name:
            summary_rows += fetch_report(slug_id, start_s, end_s)

    # ── Individual market reports: tagged with auction name ───────────────────
    print("\n── Individual Auction Markets ──")
    market_rows = []
    sheep_rows  = []
    fetched_slugs = set()
    for slug_id, auction_name in MARKET_REPORTS.items():
        if slug_id in fetched_slugs:
            continue
        fetched_slugs.add(slug_id)
        rows = fetch_report_tagged(slug_id, auction_name, start_s, end_s)
        # Route sheep/goat reports separately
        if slug_id in SHEEP_MARKET_REPORTS:
            sheep_rows += rows
        else:
            market_rows += rows

    print("\nProcessing…")
    # Summary cattle: used for statewide trend lines (feeder/replacement/slaughter)
    summary_cattle = process_cattle(summary_rows)
    # Individual market cattle: used for market comparison charts
    market_cattle  = process_cattle(market_rows)
    sheep_processed = process_sheep(sheep_rows)

    # For bracket/class charts use whichever has more data
    analysis_cattle = market_cattle if len(market_cattle) > len(summary_cattle) else summary_cattle

    markets = sorted(set(r["market"] for r in market_cattle if r["market"]))
    all_dates = sorted(set(r["date"] for r in (summary_cattle or market_cattle) if r["date"]))
    latest_date = all_dates[-1] if all_dates else end_s

    manifest = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_data_date": latest_date,
        "history_days": HISTORY_DAYS,
        "tx_markets": markets,
    }

    print("Saving…")
    def save(filename, data):
        path = os.path.join(DATA_DIR, filename)
        # Delete first so Windows/OneDrive can't leave null-byte residue from
        # a previously larger file being overwritten with a smaller one.
        if os.path.exists(path):
            os.remove(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",",":"))
        count = len(data) if isinstance(data,list) else (len(data.get("dates",[])) if isinstance(data,dict) and "dates" in data else "—")
        print(f"  ✓ {filename:35s} {str(count):>6}  ({os.path.getsize(path)/1024:.1f} KB)")

    save("manifest.json",              manifest)
    # Trend charts — prefer summary rollup; fall back to pooled market data
    trend_src = summary_cattle if summary_cattle else market_cattle
    feeder_trend      = build_trend(trend_src, "Feeder Cattle")
    replacement_trend = build_trend(trend_src, "Replacement Cattle")
    slaughter_trend   = build_trend(trend_src, "Slaughter Cattle")
    save("feeder_trend.json",          feeder_trend)
    save("replacement_trend.json",     replacement_trend)
    save("slaughter_trend.json",       slaughter_trend)
    # Market comparison — individual auction data
    save("market_week_prices.json",    build_market_week_prices(market_cattle))
    # Weight / class breakdowns
    save("weight_bracket_steers.json", build_bracket_matrix(analysis_cattle, "Steers"))
    save("weight_bracket_heifers.json",build_bracket_matrix(analysis_cattle, "Heifers"))
    save("class_breakdown.json",       build_class_matrix(analysis_cattle))
    save("cattle_latest.json",         cattle_latest_week(analysis_cattle))
    # commodity_latest pulls from trends so bar chart matches trend line endpoints exactly
    save("commodity_latest.json",      build_commodity_latest(feeder_trend, replacement_trend, slaughter_trend))
    save("sheep_compact.json",         sheep_processed)

    print(f"\n✅ Done. {len(summary_cattle):,} summary rows + {len(market_cattle):,} market rows processed.\n")

if __name__ == "__main__":
    main()
