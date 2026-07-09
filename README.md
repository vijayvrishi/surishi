# Surishi Pharmaceuticals Marketing Execution App

Mobile + web app for Surishi Pharmaceuticals marketing execution: monthly Excel-driven
task tracking, sales collection vs targets, performance analytics, and reporting.

See `memory/PRD.md` for full product history and `memory/test_credentials.md` for seeded
demo accounts.

## Structure

- `backend/` — FastAPI + MongoDB (motor) API, JWT auth, Excel parsing (openpyxl), PDF
  reports (reportlab). All routes under `/api`. OpenAPI spec at `backend/openapi.json`
  (also served live at `/docs`).
- `frontend/` — React + Vite web app (dashboard, tasks, reports, performance, profile,
  user management). The original Expo/React Native app source was never included in
  the project export, so this is a from-scratch web rebuild of the same feature set.

## Backend setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # set MONGO_URL, DB_NAME, JWT_SECRET
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Requires a running MongoDB instance (`MONGO_URL` in `.env`).

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_BACKEND_URL to the backend's URL
npm run dev
```

## Tests

```bash
cd backend
pytest tests/
```
