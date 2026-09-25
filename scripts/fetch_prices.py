#!/usr/bin/env python3
"""Writes data/prices.json with Brent and WTI.

Route 1 (primary): Yahoo Finance chart endpoint for front-month futures (BZ=F, CL=F).
  Unofficial and unversioned -> marked provisional. Near-live (delayed quotes).
Route 2 (fallback): EIA open data, daily spot prices (RBRTE, RWTC). Official, lags ~1 week.
  Only used if the repo secret EIA_API_KEY is set (free key from eia.gov/opendata).

Fails loudly in the log, silently on the wall: if both routes fail, the previous
prices.json is left untouched and the script exits non-zero.
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timezone

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "prices.json")
UA = {"User-Agent": "Mozilla/5.0 (oil-market-watch dashboard; GitHub Action)"}
SYMBOLS = [("BRENT", "Brent", "BZ=F", "RBRTE"), ("WTI", "WTI", "CL=F", "RWTC")]


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_yahoo():
    items = []
    for sym, name, ysym, _ in SYMBOLS:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(ysym) + "?range=1mo&interval=1d"
        d = get_json(url)
        res = d["chart"]["result"][0]
        meta = res["meta"]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") if len(closes) < 2 else closes[-2]
        if price is None:
            raise ValueError("no price for " + ysym)
        items.append({"sym": sym, "name": name, "price": round(price, 2),
                      "prev": round(prev, 2) if prev else None,
                      "time_utc": iso(meta.get("regularMarketTime", 0)),
                      "spark": [round(c, 2) for c in closes[-30:]]})
        print("yahoo ok", ysym, price)
    return {"source": "Yahoo Finance futures (unofficial, delayed)", "provisional": True, "items": items}


def from_eia():
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EIA_API_KEY not set - fallback unavailable")
    q = [("api_key", key), ("frequency", "daily"), ("data[0]", "value"),
         ("sort[0][column]", "period"), ("sort[0][direction]", "desc"), ("length", "80")]
    for _, _, _, series in SYMBOLS:
        q.append(("facets[series][]", series))
    d = get_json("https://api.eia.gov/v2/petroleum/pri/spt/data/?" + urllib.parse.urlencode(q))
    rows = d["response"]["data"]
    items = []
    for sym, name, _, series in SYMBOLS:
        pts = sorted([r for r in rows if r.get("series") == series], key=lambda r: r["period"])
        if len(pts) < 2:
            raise ValueError("EIA returned too few points for " + series)
        vals = [float(r["value"]) for r in pts]
        items.append({"sym": sym, "name": name, "price": round(vals[-1], 2), "prev": round(vals[-2], 2),
                      "time_utc": pts[-1]["period"] + "T00:00:00Z", "spark": vals[-30:]})
        print("eia ok", series, vals[-1], pts[-1]["period"])
    return {"source": "U.S. EIA daily spot (official, ~1 week lag)", "provisional": False, "items": items}


def main():
    out = None
    for fn in (from_yahoo, from_eia):
        try:
            out = fn()
            break
        except Exception as e:  # keep going to the next route
            print("route failed:", fn.__name__, "->", repr(e))
    if not out:
        print("ALL PRICE ROUTES FAILED - keeping last prices.json")
        sys.exit(1)
    out["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("prices.json written:", out["source"])


if __name__ == "__main__":
    main()
