#!/usr/bin/env python3
"""USDA MARS refresh for the index-reset pricing backtest.

Free API key (one-time signup): https://mymarketnews.ams.usda.gov/mymarketnews-api
Paste the key below, then run weekly after Tuesday's issue posts:

    python3 usda_refresh.py

Writes usda_data.js next to xl-roma-pricing-backtest.html. The app loads it
automatically on open. To see the raw field names a report returns before
trusting the matcher, run:

    python3 usda_refresh.py --inspect xl_roma
"""

import base64
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API_KEY = os.environ.get("MARS_API_KEY", "")  # set as a secret in CI, or paste here for local runs
BEGIN = "11/01/2023"  # pull start; MMN holds full shipping point history
END = datetime.date.today().strftime("%m/%d/%Y")
OUT = "usda_data.js"
SEED = 4  # must match the app

# Each profile: slug = MMN report id, q_commodity = API commodity filter,
# must = lowercase tokens that all have to appear somewhere in a price row
# for it to count as this spec, fallback = tokens for the backup district.
# Verify slugs once in My Market News; 1662 is National Shipping Point Trends.
COMMODITIES = {
    "xl_roma": {
        "label": "XL Roma tomatoes",
        "slug": "1662",
        "q_commodity": "Tomatoes, Plum Type",
        "must": ["roma", "25", "loose", "extra large", "texas"],
        "fallback": ["roma", "25", "loose", "extra large", "nogales"],
    },
    "round_vine": {
        "label": "Round tomatoes, vine ripe 5x6",
        "slug": "1662",
        "q_commodity": "Tomatoes",
        "must": ["vine", "2 layer", "5x6", "texas"],
        "fallback": ["vine", "2 layer", "5x6", "nogales"],
    },
    "grape": {
        "label": "Grape tomatoes, 20 lb loose",
        "slug": "1662",
        "q_commodity": "Tomatoes, Grape Type",
        "must": ["20", "loose", "texas"],
        "fallback": ["20", "loose", "nogales"],
    },
    "limes": {
        "label": "Limes, seedless 200s",
        "slug": "1662",
        "q_commodity": "Limes",
        "must": ["seedless", "200", "texas"],
        "fallback": [],
    },
    "avocado": {
        "label": "Avocados, Hass 48s",
        "slug": "1662",
        "q_commodity": "Avocados",
        "must": ["hass", "48", "texas"],
        "fallback": [],
    },
    "cukes": {
        "label": "Cucumbers, medium",
        "slug": "1662",
        "q_commodity": "Cucumbers",
        "must": ["1 1/9", "medium", "texas"],
        "fallback": ["1 1/9", "medium", "nogales"],
    },
}


def fetch(slug, query):
    url = "https://marsapi.ams.usda.gov/services/v1.2/reports/" + slug
    if query:
        url += "?q=" + urllib.parse.quote(query, safe="=;:,/ ")
    req = urllib.request.Request(url)
    token = base64.b64encode((API_KEY + ":").encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if isinstance(payload, dict):
        for key in ("results", "data", "rows"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        return []
    return payload if isinstance(payload, list) else []


def hay(row):
    return " ".join(str(v).lower() for v in row.values() if v is not None)


def num_field(row, *needles):
    for k, v in row.items():
        lk = k.lower()
        if all(n in lk for n in needles):
            try:
                return float(str(v).replace(",", "").replace("$", ""))
            except (TypeError, ValueError):
                continue
    return None


def date_field(row):
    for k, v in row.items():
        lk = k.lower()
        if "date" in lk and ("begin" in lk or "report" in lk):
            for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(str(v)[:10], fmt).date()
                except ValueError:
                    continue
    return None


def mid_mostly(row):
    lo = num_field(row, "mostly", "low")
    hi = num_field(row, "mostly", "high")
    if lo is None or hi is None:
        lo = num_field(row, "low")
        hi = num_field(row, "high")
    if lo is None and hi is None:
        return None
    if lo is None:
        return hi
    if hi is None:
        return lo
    return (lo + hi) / 2.0


def monday_of(d):
    return d - datetime.timedelta(days=d.weekday())


def build_series(rows, must, fallback):
    weeks = {}
    for row in rows:
        d = date_field(row)
        if d is None:
            continue
        text = hay(row)
        primary = all(t in text for t in must)
        backup = bool(fallback) and all(t in text for t in fallback)
        if not primary and not backup:
            continue
        mid = mid_mostly(row)
        if mid is None or mid <= 0:
            continue
        wk = monday_of(d)
        slot = weeks.setdefault(wk, {"p": [], "f": []})
        slot["p" if primary else "f"].append(mid)
    if not weeks:
        return None
    keys = sorted(weeks)
    grid, real = [], []
    cur, last = keys[0], keys[-1]
    prev = None
    while cur <= last:
        slot = weeks.get(cur)
        vals = (slot or {}).get("p") or (slot or {}).get("f") or []
        if vals:
            vals.sort()
            prev = vals[len(vals) // 2]
            grid.append(round(prev, 2))
            real.append(1)
        elif prev is not None:
            grid.append(round(prev, 2))
            real.append(0)
        cur += datetime.timedelta(days=7)
    anchor = (keys[0] + datetime.timedelta(days=1)).isoformat()
    return {"anchor": anchor, "weekly": grid, "real": real[SEED:]}


def inspect(key):
    prof = COMMODITIES[key]
    since = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%m/%d/%Y")
    q = "report_begin_date=%s:%s;commodity=%s" % (since, END, prof["q_commodity"])
    rows = fetch(prof["slug"], q)
    print("rows returned:", len(rows))
    for row in rows[:3]:
        print(json.dumps(row, indent=1, default=str))
    if rows:
        print("fields:", sorted(rows[0].keys()))


def main():
    if not API_KEY:
        sys.exit("Paste your MARS API key into API_KEY first.")
    if len(sys.argv) > 2 and sys.argv[1] == "--inspect":
        inspect(sys.argv[2])
        return
    out = {}
    for key, prof in COMMODITIES.items():
        q = "report_begin_date=%s:%s;commodity=%s" % (BEGIN, END, prof["q_commodity"])
        try:
            rows = fetch(prof["slug"], q)
        except Exception as exc:
            print(key, "fetch failed:", exc)
            continue
        series = build_series(rows, prof["must"], prof.get("fallback", []))
        if series is None:
            print(key, ": no rows matched the spec tokens; run --inspect", key)
            continue
        prints = sum(series["real"]) + SEED
        print(key, ":", len(series["weekly"]), "weeks,", prints, "USDA prints,",
              "anchor", series["anchor"])
        out[key] = series
    if not out:
        sys.exit("Nothing written.")
    with open(OUT, "w") as fh:
        fh.write("window.USDA_DATA=" + json.dumps(out) + ";\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
