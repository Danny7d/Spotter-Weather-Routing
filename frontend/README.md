# Spotter frontend

Spotter is a weather-aware truck routing workspace for planning freight trips, comparing route risk, and reviewing forecast conditions along a route.

## Local development

1. Copy `.env.example` to `.env` and set a public Mapbox token in `VITE_MAPBOX_TOKEN` for map rendering.
2. Start the backend API at `http://localhost:8000`.
3. Run `npm install` and `npm run dev` from this directory.

## Checks

- `npm test` runs the frontend unit tests.
- `npm run build` type-checks and creates the production frontend bundle.
- `npm run lint` runs Oxlint.
