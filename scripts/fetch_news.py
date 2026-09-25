#!/usr/bin/env python3
"""Writes data/news.json from public RSS feeds.

A feed that fails is skipped (logged); the file is written as long as at least one
feed returned items. If every feed fails, the previous news.json is kept.
Times are converted to UAE time (GST, UTC+4) with the correct calendar date.
"""
import json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "news.json")
UA = {"User-Agent": "Mozilla/5.0 (oil-market-watch dashboard; GitHub Action)"}
GST = timezone(timedelta(hours=4))
MAX_ITEMS = 20
MAX_AGE_DAYS = 4

# (label, url, filter_by_keywords)
FEEDS = [
    ("Google News", "https://news.google.com/rss/search?q=%28oil+OR+crude+OR+OPEC+OR+Brent+OR+tanker+OR+Hormuz%29+when%3A2d&hl=en-US&gl=US&ceid=US:en", True),
    ("OilPrice.com", "https://oilprice.com/rss/main", True),
    ("gCaptain", "https://gcaptain.com/feed/", True),
    ("Rigzone", "https://www.rigzone.com/news/rss/rigzone_latest.aspx", False),
    ("EIA Today in Energy", "https://www.eia.gov/rss/todayinenergy.xml", False),
]
KEYWORDS = re.compile(r"\b(oil|crude|opec\+?|brent|wti|tanker|tankers|hormuz|barrel|refiner\w*|petroleum|lng|bab el-mandeb|red sea|suez|shipping)\b", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def parse_feed(raw, label, filt):
    root = ET.fromstring(raw)
    items = []
    atom = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall(".//item") or root.findall(".//" + atom + "entry")
    for it in nodes:
        title = (it.findtext("title") or it.findtext(atom + "title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not link:
            ln = it.find(atom + "link")
            link = ln.get("href", "") if ln is not None else ""
        when = parse_date(it.findtext("pubDate") or it.findtext(atom + "updated") or it.findtext(atom + "published"))
        source = label
        src_el = it.find("source")
        if label == "Google News":  # titles look like "Headline - Publisher"
            fallback = label
            m = re.match(r"^(.*)\s+-\s+([^-]{2,60})$", title)
            if m:
                title, fallback = m.group(1).strip(), m.group(2).strip()
            has_src = src_el is not None and (src_el.text or "").strip()
            source = src_el.text.strip() if has_src else fallback
        if not title or not when:
            continue
        if filt and not KEYWORDS.search(title):
            continue
        items.append({"title": title, "source": source, "link": link, "when": when})
    return items


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower())[:70]


def main():
    all_items, ok = [], 0
    for label, url, filt in FEEDS:
        try:
            got = parse_feed(fetch(url), label, filt)
            print("feed ok:", label, len(got))
            all_items += got
            ok += 1
        except Exception as e:
            print("feed skipped:", label, "->", repr(e))
    if ok == 0 or not all_items:
        print("NO FEEDS RETURNED ITEMS - keeping last news.json")
        sys.exit(1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    seen, out = set(), []
    for it in sorted(all_items, key=lambda x: x["when"], reverse=True):
        k = norm(it["title"])
        if k in seen or it["when"] < cutoff:
            continue
        seen.add(k)
        g = it["when"].astimezone(GST)
        out.append({"title": it["title"], "source": it["source"], "link": it["link"],
                    "time_utc": it["when"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "gst": g.strftime("%d %b · %H:%M")})
        if len(out) >= MAX_ITEMS:
            break
    doc = {"updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "feeds_ok": ok, "items": out}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    print("news.json written:", len(out), "items from", ok, "feeds")


if __name__ == "__main__":
    main()
