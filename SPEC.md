# Surishi Pharmaceuticals — Marketing Execution App: Specification

Live at **https://app.surishi.in** · Repo: `vijayvrishi/surishi` · API spec: `backend/openapi.json` (Swagger UI at `/docs`)

## 1. Overview

Web application for Surishi Pharmaceuticals (surishi.in) that replaces a monthly
Excel-driven process for marketing execution: task assignment and tracking,
sales collection vs targets, brand/territory/management performance analytics,
and periodic reporting with PDF export.

## 2. Users & Roles

Eight roles, JWT email+password auth. All demo accounts seeded on backend startup
(see `memory/test_credentials.md`).

| Role | Admin* | User management |
|---|---|---|
| chairman | ✅ | ✅ (exclusive) |
| marketing_head | ✅ | — |
| marketing_deputy_head | ✅ | — |
| product_executive, general_manager, ceo, agm, business_manager | — | — |

*Admin = upload Excel sheets, create/delete tasks.

- Any user: view all data, update task status, enter collected amounts, attach
  photos, change own password.
- Chairman only: change any user's role/name/HQ, reset passwords, delete users
  (self-delete blocked).

## 3. Functional Modules

### 3.1 Authentication
- Register (name, email, password ≥6 chars, role picker, optional HQ) and login.
- JWT (HS256, 7-day expiry) returned as `access_token` with public user object.
- Change own password; chairman can reset any password.
- Forgot password (admin-mediated): "Forgot password?" on the login screen files
  a reset request (same generic response whether or not the email exists, to
  avoid leaking accounts). Chairman sees pending requests at the top of the
  Users screen and resets from there; completing a reset auto-clears the
  request. No email service is involved.

### 3.2 Tasks
Fields: title, description, assignee, role, HQ, frequency (bucket:
`daily|weekly|monthly|quarterly|yearly|ongoing|scheduled|other` plus the
original free-text `frequency_label`, e.g. "Per CME schedule"),
`activity_category` (free-text functional grouping, e.g. "CME planning",
"Collections"), category (`task|sales_collection|target`, auto-derived from
the activity grouping), activity head (`company|scientific_inputs|engagement`),
start/due/reporting-due dates, target amount, collected amount, status
(`pending|in_progress|completed`), photos (≤10, base64 ≤4 MB each), derived
`month` from due date.

Recurring tasks with no explicit date are anchored to the first day of the
concerned period (monthly → 1st of month, quarterly → 1st of quarter, etc.)
so they appear in period-scoped dashboards and reports; non-periodic
frequencies (ongoing / as-scheduled) stay undated.

- List with filters: frequency, status, HQ, category, head, assignee, role,
  period (`week|month|quarter`), free-text title search.
- Detail view: all fields, status chips, collected-amount entry for sales
  items, photo gallery (upload/fullscreen/delete).
- **Per-assignee completion**: a task can list multiple participants
  (`units` — e.g. the BM/GM of each HQ). Each participant marks their own
  status via `PATCH /tasks/{id}/completion`; the overall task status is
  **derived** and only becomes "completed" when every participant has
  completed it. The detail page shows a completion donut/progress graph and a
  per-assignee breakdown; the task list shows an "X/N" completion count.
  Tasks with no `units` keep the simple single-status behaviour. Participants
  can be entered on the create form or via an "Assignees"/"HQ List" Excel
  column.
- Admin: manual create, delete.
- **Excel bulk upload** (admin): `.xlsx/.xlsm`; the header row is auto-located
  (a title/banner row above the headers is fine), and columns are matched
  flexibly (e.g. "Task Name"/"Activity" → title, "Start / Due Date"/"Deadline"
  /"Timeline" → due date, "Category"/"Activity Area" → activity_category); rows
  missing a task name are reported back as skipped with row numbers. Verified
  against the production task sheet (Assignee, Task Name, Description, Frequency,
  Start / Due Date, Category, Reporting Due Date).

### 3.3 Dashboard
Current-month KPIs (total/completed/in-progress/pending/overdue/completion %),
sales collected vs target progress, today's focus list (due today + open daily
tasks), 5 most recent tasks, admin quick actions.

### 3.4 Reports
- Periods: week / month / quarter (UTC-based ranges).
- Status donut chart; sales vs target; completion breakdowns by HQ, assignee,
  role, frequency, and activity head — every row drills down to the underlying
  task list.
- **PDF download** (`reportlab`): KPIs, sales, all breakdowns, plus latest
  performance data (brand table, MoM growth, territory region summary,
  management KPIs).

### 3.5 Performance Module
Separate Excel upload (admin) that auto-detects one of three sheet formats and
parses **all month-named tabs** in the workbook (re-upload replaces that
month's data — idempotent):

1. **Brand Performance** — brand, target, W1–W4 sales, computed achievement %,
   top/lowest territory.
2. **Territory Performance** — region → HQ rows with BE/KAM name, DOJ, target,
   weekly secondary sales, achievement %.
3. **Management Dashboard** — primary/secondary sales, run rate, active
   doctors, new prescribers (weekly + total), weekly top/lowest brand and
   strong/weak territory.

Views: month chips + Brands (W1–W4 trend bars, achievement badges),
Territories (grouped by region with totals), Management (KPI cards),
**Growth** (brand-wise month-over-month: bar chart per brand, per-month growth
%, overall growth badge).

### 3.6 Profile & User Management
Profile: user info, admin shortcuts, change password, logout.
Users & Access screen (chairman): edit role/name/HQ, reset password, delete;
plus **Feature Access** and a Danger Zone (clear all data).

### 3.7 Feature Access (chairman-controlled RBAC)
The chairman decides, per role, which features (Dashboard, Tasks, Performance,
Reports) each role can see, via a role × feature checkbox matrix on the Users &
Access screen (`GET/PUT /api/admin/permissions`). Profile is always visible;
Users & Access is chairman-only; the chairman always has full access. Access is
enforced on the **backend** — the relevant endpoints are gated with a
`require_feature(...)` dependency returning 403 — and reflected in the UI: the
sidebar hides disallowed features and direct navigation to a hidden route
redirects to the user's first allowed screen. Each client reads its own allowed
set from `GET /api/me/features`. Defaults to all-on for every role.

## 4. Architecture

```
Browser ── https://app.surishi.in
              │  (GoDaddy A record → 3.6.111.165, Let's Encrypt TLS, HTTP→HTTPS)
        ┌─────▼──────────────────────────────┐
        │ EC2 t3.micro (ap-south-1, AL2023)  │
        │  nginx :443/:80                    │
        │   ├─ /            → React build    │  /opt/surishi/frontend/dist
        │   ├─ /api, /docs  → 127.0.0.1:8000 │
        │  uvicorn (systemd: surishi-backend)│  /opt/surishi/backend
        └─────┬──────────────────────────────┘
              │ mongodb+srv (TLS)
        MongoDB Atlas — cluster0.jdq552k, db "surishi"
```

- **Backend**: FastAPI + motor (async Mongo), PyJWT, pwdlib/argon2, openpyxl,
  reportlab. Single file `backend/server.py`; all routes under `/api`.
- **Frontend**: React 19 + Vite, react-router, recharts, axios. Same-origin
  `/api` calls (no CORS in production). SPA fallback via nginx `try_files`.
- **Secrets**: AWS SSM Parameter Store (`/surishi/MONGO_URL`, `/surishi/DB_NAME`,
  `/surishi/JWT_SECRET`; SecureString). EC2 instance role
  `surishi-ec2-role` grants read of those parameters + SSM management access.
  No SSH port is open — administration is via AWS SSM Session/Run Command.
- **TLS**: certbot (Let's Encrypt), auto-renew via `certbot-renew.timer`.
- **Data collections**: `users`, `tasks`, `brand_performance`,
  `territory_performance`, `management_dashboard` (all keyed by app-level
  UUID `id`; performance docs keyed by `month` = `YYYY-MM`).

## 5. API Summary

Full schema: `backend/openapi.json` / live Swagger at `/docs`.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password`, `POST /api/auth/forgot-password` |
| Users | `GET /api/users`, `GET /api/me/features`; chairman: `PATCH /api/admin/users/{id}`, `POST /api/admin/users/{id}/reset-password`, `DELETE /api/admin/users/{id}`, `GET/DELETE /api/admin/reset-requests[/{id}]`, `GET/PUT /api/admin/permissions`, `DELETE /api/admin/data` |
| Tasks | `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}`, `PATCH /api/tasks/{id}/completion` (per-assignee), `POST /api/tasks/upload`, photos: `POST /api/tasks/{id}/photos`, `DELETE /api/tasks/{id}/photos/{photoId}` |
| Dashboard/Reports | `GET /api/dashboard`, `GET /api/reports?period=`, `GET /api/reports/pdf?period=`, `GET /api/meta/filters` |
| Performance | `POST /api/performance/upload`, `GET /api/performance/months|brands|territories|management|growth` |

## 6. Frontend Routes

`/login`, `/register` (public) · `/` dashboard · `/tasks`, `/tasks/:id` ·
`/reports` · `/performance` · `/profile` · `/users` (chairman only).

## 7. Operations Runbook

- **Deploy an update**: push to `main`, then on the instance (via SSM):
  `cd /opt/surishi && git pull && cd frontend && npm ci && npm run build &&
  systemctl restart surishi-backend && systemctl reload nginx`
  (backend-only changes need only the git pull + service restart).
- **Backend logs**: `journalctl -u surishi-backend -f`
- **Rotate DB password**: update in Atlas → update SSM param
  `/surishi/MONGO_URL` → regenerate `/opt/surishi/backend/.env` from SSM →
  `systemctl restart surishi-backend`.
- **Local development**: see `README.md` (backend: uvicorn + `.env`;
  frontend: `npm run dev` with `VITE_BACKEND_URL`).

## 8. Known Limits / Backlog

- Photos stored as base64 inside task documents (Mongo 16 MB doc limit caps
  ~10×4 MB loosely; consider S3/GridFS if usage grows).
- t3.micro single instance — no HA; upgrade instance or add a load balancer if
  usage grows.
- Backlog from PRD: per-assignee "My Tasks" linking accounts to Excel assignee
  names, Excel export of reports, overdue reminders, monthly archive view.
