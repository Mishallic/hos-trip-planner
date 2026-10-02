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
| `hos-trip-planner-api` | `backend` | Detected as Django. Set `DJANGO_SECRET_KEY`. Python version comes from `.python-version`. |
| `hos-trip-planner-web` | `frontend` | Detected as Vite. `vercel.json` rewrites `/api/*` to the API project, so the browser only talks to one origin and no CORS is needed. |

Check a deployment with `GET /api/health`, which returns `{"status": "ok", "python": "<version>"}`.
