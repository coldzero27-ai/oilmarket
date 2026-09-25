# Oil Market Watch — wall dashboard

A full-screen oil market board for an office TV: a live ship map fills the screen, with
glass cards on top for oil prices, top producers, headlines and chokepoint traffic.
All times are UAE time (GST, UTC+4).

## Files

```
index.html                         the dashboard (single file)
data/prices.json                   Brent + WTI      — written by the Action
data/news.json                     oil headlines    — written by the Action
data/chokepoints.json              chokepoint flows — written by the Action
data/stats.json                    Statista figures — updated by hand (see below)
scripts/fetch_prices.py            price fetcher (Python, no installs)
scripts/fetch_news.py              RSS headline fetcher
scripts/fetch_chokepoints.py       IMF PortWatch fetcher
.github/workflows/refresh-data.yml runs the three fetchers every 30 min
.nojekyll                          serve files as-is
```

## Setup (one time)

1. Create a repo and upload everything, keeping the folder structure
   (the workflow **must** sit at `.github/workflows/refresh-data.yml`).
2. Settings → Pages → Deploy from branch → `main` / root.
3. Settings → Actions → General → Workflow permissions → **Read and write**.
4. Actions tab → enable workflows if asked → "Refresh oil data" → **Run workflow**.
   A green tick and a new "data: refresh" commit mean the data files are live.
5. Optional, recommended: get a free key at eia.gov/opendata and add it as the repo
   secret `EIA_API_KEY`. It is the official fallback if the primary price source fails.

Open the Pages URL on the TV. Opening `index.html` by double-click will not load the
data files (browsers block that) — always use the Pages link.

## Where each number comes from, and how fresh it is

| Card | Source | Cadence |
|---|---|---|
| Ship map | Provider's live embed (VesselFinder / MyShipTracking / MarineTraffic) | Live, provider-side |
| Brent, WTI | Yahoo Finance futures (unofficial, delayed quotes); fallback U.S. EIA daily spot (official, ~1 week lag) | Every 30 min |
| Headlines | Google News, OilPrice.com, gCaptain, Rigzone, EIA RSS | Every 30 min |
| Chokepoints | IMF PortWatch daily transits (modelled from AIS) | PortWatch publishes weekly (Tuesdays) — latest day is usually 1–2 weeks old |
| Producers, Brent 2026 chart | Statista (Energy Institute; weekly spot) | Manual snapshot |

GitHub may delay scheduled runs by several minutes. A card whose file is too old shows
"stale" instead of pretending to be current. If a source fails, the last good file stays.

## URL options (bookmark one per screen)

`?map=vf|mst|mst-sat|mt`  `&view=gulf|region|world`  `&glass=dark|heavy|light`  `&present=1`

## Updating the Statista figures

`data/stats.json` is edited by hand (ask Claude to re-pull via the Statista connector).
Keep the structure: `producers_2025.values` is a list of `["Country", value]` pairs,
highest first; `brent_weekly_2026.values` is a list of numbers.

## Notes

- The map provider's logo appears inside the map; it cannot be removed.
- The map shows all vessel types; the free embeds cannot filter to tankers.
- Private repos: the 30-minute schedule uses roughly 1,500 of the 2,000 free Actions
  minutes per month. Public repos have no limit.
- Check that your Statista licence allows displaying its figures on a screen.

Coastline and map data belong to the respective embed providers. IMF PortWatch data:
IMF terms. Statista data: Statista terms.
