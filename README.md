# Spotter — Weather-Aware Truck Routing

A full-stack application that generates up to three alternative truck routes,
samples weather forecasts at checkpoints along each route, classifies travel
risk, and recommends the safest route — with a forecast slider and a
route weather-risk overlay on an interactive map.

## Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS + Mapbox GL JS (`frontend/`)
- **Backend**: Django + Django REST Framework (`backend/`)
- **Routing**: Mapbox Directions API (up to 3 alternatives)
- **Geocoding**: Mapbox Geocoding API v6 (via backend proxy)
- **Weather**: Open-Meteo forecast API (no key required)
- **Timezones**: `timezonefinder` resolves the origin's IANA timezone from coordinates

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Add MAPBOX_ACCESS_TOKEN to backend/.env
python manage.py runserver
```

API runs at `http://localhost:8000`. `MAPBOX_ACCESS_TOKEN` is required for
routing and geocoding; without it those endpoints return a clear error while
the rest of the app (and all tests) still works.

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env
# Add VITE_MAPBOX_TOKEN to frontend/.env
npm run dev
```

Vite serves the frontend at `http://localhost:5173` and proxies `/api` to
`http://localhost:8000`.

`VITE_MAPBOX_TOKEN` is a **public** Mapbox token used only to render map
tiles in the browser — restrict it by URL in the Mapbox dashboard. The
Directions/Geocoding token (`MAPBOX_ACCESS_TOKEN`) stays server-side only.

## API contract

| Endpoint | Purpose |
|---|---|
| `POST /api/plan/` | Full trip plan: routes, checkpoints, weather, risk, metrics, ranking, recommendation |
| `GET /api/geocode/?q=` | Place search (proxied to Mapbox) |
| `POST /api/corridor-forecast/` | Hourly risk series along route sample points (0–48 h) for the overlay |
| `GET /api/health/` | Liveness check |

`POST /api/plan/` body:

```json
{
  "origin": "Dallas, TX",
  "destination": "Austin, TX",
  "departure_local": "2026-11-25T08:00:00",
  "load_weight_lbs": 30000,
  "checkpoint_interval_miles": 25
}
```

`departure_local` is interpreted in the **origin's IANA timezone** (resolved
from coordinates via timezonefinder), converted to UTC, and all checkpoint
ETAs are computed in UTC. The response echoes `origin_timezone` and
`departure_utc` so the interpretation is verifiable.

## Risk methodology

### Checkpoint classification

Each checkpoint's weather is classified against these thresholds. Lower
bounds belong to the category shown, so boundary values move into the higher
risk category. The highest category's upper bound is inclusive where shown.
Rain intensity combines Open-Meteo `rain` and `showers`; snow uses
`snowfall`.

| Weather measure | Low | Moderate | High | Severe | No Travel |
|---|---:|---:|---:|---:|---:|
| Wind (mph) | < 25 | 25–<35 | 35–<45 | 45–<55 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10–<0.25 | 0.25–<0.50 | 0.50–1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5–<1.0 | 1.0–<2.0 | 2.0–3.0 | > 3.0 |

The checkpoint level is the highest risk among wind, rain, and snow. Load
rules can raise severity further:

- wind ≥ 55 mph → **No Travel** for every load
- wind 45–54 mph and load > 30,000 lb → **No Travel**
- wind 35–44 mph and load > 40,000 lb → **Severe**

### Checkpoint → route mileage metrics

For each segment between consecutive checkpoints, the segment is assigned
the **worse** of its two endpoint risk levels and weighted by segment
distance:

- `severe_miles` / `high_miles` / `no_travel_miles`: summed segment miles per category
- `average_risk_score`: distance-weighted mean of low=1 … no_travel=5 over
  segments with known weather
- `weather_coverage`: fraction of route miles with known weather; unknown
  weather is excluded from the average and reported via `status:
  "incomplete"` — it is never treated as Low risk

### Ranking (lexicographic)

1. Routes containing any No Travel segment always sort last and are never
   recommended.
2. Fewest Severe miles.
3. Fewest High miles.
4. Lowest average risk score.
5. Shortest travel time.
6. Distance, then route id (deterministic tie-breakers).

If every route contains No Travel conditions the API returns
`recommendation.safe = false` with an explanatory message.

## Weather-risk overlay & forecast slider

The map overlay is a **route weather-risk overlay**: the selected route's
geometry is sampled every few miles, hourly Open-Meteo forecasts (0–48 h)
are fetched in one batched request, classified with the same risk engine,
and rendered as risk-colored segments. The slider selects the forecast hour;
segments are colored by the worse risk of their two endpoints — the same
methodology as route metrics. It is derived from model forecast data, not a
continuous observed weather raster, and the UI labels it accordingly.

## Tests and production build

```bash
cd backend
.venv/bin/pytest
```

The backend suite currently passes **102 tests**. It covers risk thresholds,
load rules, unit conversions, checkpoint generation and ETAs, route metrics
and ranking, missing weather, and API validation and error paths.

```bash
cd frontend
npm ci
npm test
npm run build
```

The frontend suite currently passes **10 tests** across two test files. The
production build runs TypeScript checking and Vite bundling.

## Deployment

### Backend (Render)

Deploy as a Web Service using `render.yaml` or through the Render Dashboard.
The blueprint sets the root directory to `backend`, installs
`backend/requirements.txt`, and starts Gunicorn with the command below:

- **Runtime**: Python (Render-managed)
- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`

**Environment Variables**:
The backend refuses to start in production (`DJANGO_DEBUG=false`) if
`DJANGO_SECRET_KEY`, `MAPBOX_ACCESS_TOKEN`, or `DJANGO_ALLOWED_HOSTS` is
missing. Set `CORS_ALLOWED_ORIGINS` to the deployed frontend origin so browser
requests are allowed. `EXTERNAL_API_TIMEOUT_SECONDS` is optional.

- `DJANGO_SECRET_KEY`: A cryptographically secure secret key (do not use the default dev key).
- `DJANGO_DEBUG`: Must be set to `false`.
- `DJANGO_ALLOWED_HOSTS`: Comma-separated allowed hostnames (e.g. `your-service.onrender.com`).
- `MAPBOX_ACCESS_TOKEN`: Server-side Mapbox access token for Directions and Geocoding APIs.
- `CORS_ALLOWED_ORIGINS`: Comma-separated allowed frontend origins (e.g. `https://your-frontend.vercel.app`).
- `EXTERNAL_API_TIMEOUT_SECONDS`: (Optional) Timeout for outbound external requests in seconds (default: 20).

### Frontend (Vercel)

Deploy the `frontend` directory as a Vite / React project on Vercel. No
`vercel.json` is present; set the project options as follows:

- **Framework Preset**: Vite
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

**Required Environment Variables**:
- `VITE_MAPBOX_TOKEN`: Public Mapbox token (`pk.*`) used for browser map tiles. Can be restricted to your domain in the Mapbox console.
- `VITE_API_BASE_URL`: Full base URL of your deployed Render backend (e.g. `https://your-service.onrender.com`). If empty or omitted during development, Vite proxies `/api` to `http://localhost:8000`.

### Map loading

The route map is loaded asynchronously with `React.lazy()` and a dynamic
import. A placeholder is shown while the map component loads.


## Known limitations

- Open-Meteo forecasts extend ~16 days; departures beyond that yield
  `unknown` risk at affected checkpoints (reported via weather coverage).
- Checkpoint ETAs assume constant average speed along each route
  (distance-proportional interpolation of total duration).
- The risk overlay samples the route at discrete points rather than
  interpolating a full weather field.
