# Surishi Pharmaceuticals Marketing Execution App

Mobile + web app for Surishi Pharmaceuticals marketing execution: monthly Excel-driven
task tracking, sales collection vs targets, performance analytics, and reporting.

See `memory/PRD.md` for full product history and `memory/test_credentials.md` for seeded
demo accounts.

## Structure

- `backend/` — FastAPI + MongoDB (motor) API, JWT auth, Excel parsing (openpyxl), PDF
  reports (reportlab). All routes under `/api`.
- `frontend/` — Expo Router React Native app (**source not yet in this repo** — the
  original export only included build config/cache, not the app source. Needs to be
  re-exported or rebuilt).

## Backend setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # set MONGO_URL, DB_NAME, JWT_SECRET
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Requires a running MongoDB instance (`MONGO_URL` in `.env`).

## Tests

```bash
cd backend
pytest tests/
```
