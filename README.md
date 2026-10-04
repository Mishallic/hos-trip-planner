# HOS Trip Planner

Plan a truck trip from the driver's current location through pickup to drop-off,
and get a route with every required stop and rest placed under the FMCSA
hours-of-service rules (property-carrying, 70 hours / 8 days), plus filled-in
daily log sheets for each day of the trip.

> Work in progress. Architecture, the HOS algorithm, assumptions and deployment
> notes will be documented here as they land.

## Stack

- **API:** Python 3.14, Django 6.1, Django REST Framework (`backend/`)
- **Web:** React 19, TypeScript, Vite (`frontend/`)

## Hours-of-service rules

The planner follows the FMCSA rules for a property-carrying driver on the
70-hour / 8-day schedule, as described in the FMCSA *Interstate Truck Driver's
Guide to Hours of Service* (April 2022). Code and tests cite it as "guide p. N".

| Rule | Limit | Guide |
|---|---|---|
| Driving limit | 11 hours of driving after 10 hours off duty | p. 6 |
| Driving window | no driving after the 14th hour since coming on duty | p. 6 |
| Break | 30 consecutive minutes off the wheel after 8 hours of cumulative driving | p. 10 |
| Cycle | no driving after 70 hours on duty in 8 days | p. 10-11 |
| Restart | 34 consecutive hours off duty resets the cycle | p. 11 |

Every limit and assumption lives in one `HOSPolicy` object
(`backend/planner/domain/policy.py`).

### Planning decisions

Where the rules leave room, or the inputs don't say, the planner makes these
choices. Code and tests cite them as D1, D2, ...

| # | Decision |
|---|---|
| D1 | The trip has a start date and time, defaulting to now. Log sheets run midnight to midnight. |
| D2 | The whole trip uses one time zone: the home terminal's, which defaults to the current location's (guide p. 16). |
| D3 | Cycle hours used apply to the whole trip; there is no day-by-day history. Reaching 70 hours triggers a 34-hour restart. |
| D4 | A 30-minute pre-trip inspection, on duty, starts each duty period that includes driving: at the trip start and after every 10-hour rest or 34-hour restart. When the period starts at the pickup, the inspection comes before loading. It is per duty period, not per calendar day. No separate post-trip inspection is planned. |
| D5 | The 10-hour rest is logged in the sleeper berth. The 30-minute break is logged off duty. |
| D6 | The split sleeper-berth provision (guide p. 7-9) is not used. |
| D7 | A 30-minute fuel stop, on duty, comes at or before every 1,000 miles. The tank is full at the start. |
| D8 | Driving time is never planned faster than a 55 mph average, because free routers estimate car speeds. |
| D9 | Any 30 consecutive non-driving minutes count as the break, including fuel stops and pickup (guide p. 10). |
| D10 | The driver starts the trip rested, with full 11- and 14-hour clocks. The log shows off duty before the start and after drop-off. |
| D11 | The 34-hour restart is logged off duty. |
| D12 | The recap is approximate: it adds this trip's on-duty time to the cycle hours entered, because earlier days are unknown. |
| D13 | Pickup and drop-off each take 1 hour, on duty. |
| D14 | On-duty work is still allowed after the 14-hour window or the 70-hour cycle runs out; only driving stops (guide p. 6, 9-10). |
| D15 | When a break comes due and the next fuel stop would be due within the next hour of driving, the driver fuels then instead. The fuel stop counts as the break (D9), so there is one stop, not two. |
| D16 | Just before a 10-hour rest or 34-hour restart, the driver fuels if the trip needs more fuel, the tank won't last the next full shift, fuelling now doesn't add a fuel stop to the rest of the trip, and the fuel stop it replaces would not have doubled as the next shift's 30-minute break (D9). It never adds a fuel stop or lengthens the trip. Fuel still comes at or before every 1,000 miles. |
| D17 | Log sheets use the home terminal's UTC offset at the trip start for the whole trip, so every sheet is exactly 24 hours, with no 23- or 25-hour days at a daylight-saving change. |
| D18 | Remarks name each stop after the nearest place with at least 1,000 people, as "City, ST" (guide p. 17). When that place is more than 5 miles away the remark reads "near City, ST". The lookup is offline, so planning never waits on a geocoding service. |
| D19 | When a 10-hour rest comes due and the hours left in the 70-hour cycle cannot cover the rest of the trip, the 34-hour restart can be taken in place of the rest: the same driving, 10 hours sooner. It is taken early only when one restart covers the rest of the trip, or when the hours left are too few to save a restart anyway. Because the work still to come is only an estimate, the planner plans the trip three ways (this rule, restarting early only when one restart covers the rest, and never restarting early) and keeps the plan with the fewest restarts, then the earliest drop-off. It never takes more restarts or arrives later than restarting at every rest would. |

## Data and services

- Routing: [OSRM](https://project-osrm.org) public demo server.
- Place search: [Photon](https://photon.komoot.io) by komoot, with [Nominatim](https://nominatim.org) as a fallback. Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Stop names: place data from [GeoNames](https://www.geonames.org), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). `backend/scripts/build_places.py` builds the bundled file (`places_us_ca_mx.tsv.gz`) from GeoNames `cities1000`, keeping places in the US, Canada and Mexico with at least 1,000 people.
- Time zones: [timezonefinder](https://github.com/jannikmi/timezonefinder), offline.
- Map tiles: [Esri](https://www.esri.com) World Dark Gray Canvas (Esri, HERE, Garmin, © OpenStreetMap contributors), no key needed.

## Run locally

Requires Python 3.14 and Node 20+.

### API

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py runserver
```

The API listens on http://127.0.0.1:8000.

### Web

```powershell
cd frontend
npm install
npm run dev
```

The web app listens on http://localhost:5173 and proxies `/api` to the local API.

## Deploy

Both apps deploy to Vercel as two projects from this repository.

| Project | Root directory | Notes |
|---|---|---|
| `hos-trip-planner-api` | `backend` | Detected as Django. Set `DJANGO_SECRET_KEY`. Python version comes from `.python-version`. `vercel.json` runs the function in Frankfurt (`fra1`), next to the OSRM and Photon servers. |
| `hos-trip-planner-web` | `frontend` | Detected as Vite. `vercel.json` rewrites `/api/*` to the API project, so the browser only talks to one origin and no CORS is needed. |

Check a deployment with `GET /api/health`, which returns `{"status": "ok", "python": "<version>"}`.

Every plan response carries a `Server-Timing` header (`geocode`, `route`, `compute`, `total`, in ms), visible in the browser's network panel.
