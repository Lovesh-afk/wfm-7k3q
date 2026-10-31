# Wind Forecast Monitor

A small web app for a UK energy utility that buys power on the day-ahead market. It answers two questions:

1. **Decision view:** what was the latest national wind forecast available at the moment I make a purchase decision, and how uncertain is it?
2. **Forecast accuracy:** how wrong have those forecasts been, how does the error grow with forecast horizon, and when does it go wrong?

The scope is January 2026. Data comes from Elexon BMRS: actuals from `FUELHH` (fuelType `WIND`) and forecasts from `WINDFOR`.

**Live app:** https://wfm-7k3q.vercel.app

---

## Files and directories

```
.
├── api/index.py              Vercel serverless entry point (re-exports the FastAPI app)
├── backend/
│   ├── app/
│   │   ├── config.py         Dataset names, January window, horizon limits, cache TTL
│   │   ├── main.py           FastAPI app + CORS
│   │   ├── api/routes.py     HTTP endpoints (/api/analysis, /api/horizon-curve, /api/forecast-at)
│   │   ├── core/models.py    Typed dataclasses: ActualPoint, ForecastPoint, ComparisonPoint
│   │   ├── core/forecast.py  Horizon logic: "latest forecast published ≥ H hours before target"
│   │   ├── core/metrics.py   MAE, RMSE, bias, bias-corrected MAE, MAPE, P90, by-hour, histogram
│   │   └── services/elexon.py  Elexon BMRS client (httpx + in-memory TTL cache)
│   ├── tests/                pytest: pure logic tests + API tests with a fake Elexon client
│   ├── requirements.txt / requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx           Layout + two tabs
│   │   ├── components/DecisionView.jsx   Forecast at decision time with P90 band
│   │   ├── components/AccuracyView.jsx   Metrics, horizon curve, by-hour bias
│   │   ├── components/MetricCard.jsx, StatusMessage.jsx
│   │   ├── api/client.js     Fetch wrappers
│   │   ├── useApi.js         Data-loading hook (ignores stale responses)
│   │   ├── format.js         MW/GW/date formatting (UTC)
│   │   └── styles.css
│   ├── vite.config.js        Dev server proxies /api to the backend
│   ├── nginx.conf + Dockerfile   Production container (nginx serves static files, proxies /api)
├── docker-compose.yml
├── vercel.json               Builds the frontend, routes /api/* to the Python function
└── requirements.txt          Python deps for Vercel
```

## How to start the app

### Option 1: Docker (one command)

```bash
docker compose up --build
```

Then open http://localhost:8080. The API is also available at http://localhost:8000/docs.

### Option 2: Local dev

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Node 18+), in a second terminal
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

### Tests

```bash
cd backend && pytest -q
```

The tests never call Elexon. The API tests inject a fake client through FastAPI's dependency overrides.

### Deploy to Vercel

Import the repo in Vercel with no extra settings; `vercel.json` handles everything. The frontend is built to `frontend/dist`, and `api/index.py` runs FastAPI as a serverless function on the same domain, so there are no CORS issues.

---

## Design decisions

**Which forecast counts as "available at decision time"?** For each target hour T and horizon H, I use the latest `WINDFOR` forecast whose `publishTime ≤ T − H`. This is what a trader could actually have seen. It is implemented with a sort plus binary search per target hour (`core/forecast.py`). Forecasts published after their target (negative horizon) are dropped.

**Resolution.** `WINDFOR` is hourly and `FUELHH` is half-hourly. I compare on the hourly timestamps where both exist rather than interpolating the forecast.

**Fetching.** Elexon's `/stream` endpoints return the whole month in one call. Forecasts are fetched from 4 days before January so that 48-hour horizons are covered on 1 January. Results are cached in memory for 6 hours.

**Metrics.** MAE is the headline ("average miss in MW"). The app also shows:

- RMSE, which punishes big misses.
- Bias, which shows the direction of the error.
- Bias-corrected MAE, which shows the error left once the systematic offset is removed.
- P90 absolute error, which works as a safety margin.
- MAPE, only for hours where actual output is at least 500 MW, because low output inflates percentages.

The Decision view's shaded band is the P90 error at the nearest horizon.

**Key finding (January 2026).**

- Forecasts are consistently **too high, by about 1.6–1.9 GW**.
- MAE grows from about 1.8 GW at 0 h to about 2.05 GW at 24 h and about 2.4 GW at 48 h.
- P90 error at 24 h is about 4.1 GW.

A likely cause is that `WINDFOR` covers a different scope than metered `FUELHH` wind (for example embedded or curtailed generation). That is why bias-corrected MAE is shown separately: a buyer can correct the offset and is then left with the true randomness.

**Trade-offs and next steps.**

- The cache is in-memory, so it is per instance on serverless. Redis or a scheduled pre-computation into a small database would be next.
- The app has no auth.
- The band is symmetric. Separate quantiles for over- and under-forecasting would be more honest given the bias.

---

## AI usage

I used AI tools (Anthropic's Claude) while building this:

- **Used for:** scaffolding the project structure, drafting React/Recharts components and CSS, writing first drafts of tests, the Docker/Vercel config and this README, and talking through metric choices.
- **Done by me:** I reviewed, ran and adjusted all code. I checked the Elexon API responses and the analysis numbers against the real data, and I am responsible for the design decisions above.
