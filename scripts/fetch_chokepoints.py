#!/usr/bin/env python3
"""Writes data/chokepoints.json from IMF PortWatch (public ArcGIS FeatureServer).

PortWatch publishes daily transit counts per chokepoint, refreshed WEEKLY (Tuesdays,
9 AM ET), so the latest day is typically 1-2 weeks old. Counts are modelled from AIS,
not customs-verified. For each chokepoint: average daily transits over the latest 7
days vs the same 7 days one year earlier (baseline chosen so no crisis date is assumed).

Runs only if the existing file is older than MIN_HOURS (data changes weekly).
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "chokepoints.json")
BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
UA = {"User-Agent": "Mozilla/5.0 (oil-market-watch dashboard; GitHub Action)"}
MIN_HOURS = 6
# (display name, SQL LIKE pattern on portname)
POINTS = [("Strait of Hormuz", "%Hormuz%"), ("Bab el-Mandeb", "%Mandeb%"), ("Suez Canal", "%Suez%"),
          ("Malacca Strait", "%Malacca%"), ("Cape of Good Hope", "%Good Hope%")]


def fresh_enough():
    try:
        with open(OUT, encoding="utf-8") as f:
            u = json.load(f).get("updated_utc")
        if not u:
            return False
        age = datetime.now(timezone.utc) - datetime.strptime(u, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return age < timedelta(hours=MIN_HOURS)
    except Exception:
        return False


def query(pattern, since):
    params = {"where": "portname LIKE '%s' AND date >= DATE '%s'" % (pattern, since),
              "outFields": "date,portname,n_tanker,n_total", "orderByFields": "date DESC",
              "resultRecordCount": "1000", "returnGeometry": "false", "f": "json"}
    req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        d = json.loads(r.read().decode("utf-8"))
    if "error" in d:
        raise RuntimeError(d["error"])
    rows = []
    for f in d.get("features", []):
        a = f["attributes"]
        if a.get("date") is None:
            continue
        day = datetime.fromtimestamp(a["date"] / 1000, timezone.utc).date()
        rows.append((day, a.get("portname"), a.get("n_tanker") or 0, a.get("n_total") or 0))
    return rows


def avg(rows, start, end, idx):
    v = [r[idx] for r in rows if start <= r[0] <= end]
    return (round(sum(v) / len(v), 1), len(v)) if v else (None, 0)


def main():
    if fresh_enough() and "--force" not in sys.argv:
        print("chokepoints.json is fresh (<%dh) - skipping" % MIN_HOURS)
        return
    since = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d")
    items, ok = [], 0
    for name, pat in POINTS:
        try:
            rows = query(pat, since)
            if not rows:
                raise ValueError("no rows (check portname pattern)")
            names = sorted({r[1] for r in rows})
            latest = max(r[0] for r in rows)
            s7 = latest - timedelta(days=6)
            ly_end, ly_start = latest - timedelta(days=364), s7 - timedelta(days=364)
            tot7, n7 = avg(rows, s7, latest, 3)
            tan7, _ = avg(rows, s7, latest, 2)
            totly, nly = avg(rows, ly_start, ly_end, 3)
            tanly, _ = avg(rows, ly_start, ly_end, 2)
            last_day = [r for r in rows if r[0] == latest][0]
            pct = round((tot7 - totly) / totly * 100) if tot7 is not None and totly else None
            pct_t = round((tan7 - tanly) / tanly * 100) if tan7 is not None and tanly else None
            items.append({"name": name, "portname": names, "latest_date": latest.isoformat(),
                          "total_7d": tot7, "tanker_7d": tan7, "total_ly": totly, "tanker_ly": tanly,
                          "pct_total": pct, "pct_tanker": pct_t,
                          "last_day_total": last_day[3], "last_day_tanker": last_day[2],
                          "days_in_window": n7, "days_in_baseline": nly})
            ok += 1
            print("ok:", name, names, latest, "7d avg", tot7, "vs", totly)
        except Exception as e:
            print("chokepoint skipped:", name, "->", repr(e))
            items.append({"name": name, "error": True})
    if ok == 0:
        print("PORTWATCH FAILED FOR ALL - keeping last chokepoints.json")
        sys.exit(1)
    doc = {"updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "IMF PortWatch · Daily Chokepoint Transit Calls (modelled from AIS, updated weekly)",
           "items": items}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("chokepoints.json written:", ok, "of", len(POINTS))


if __name__ == "__main__":
    main()
