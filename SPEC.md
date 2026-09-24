# Surishi Pharmaceuticals — Marketing Execution App: Specification

Live at **https://app.surishi.in** · Repo: `vijayvrishi/surishi` · API spec: `backend/openapi.json` (Swagger UI at `/docs`)

## 1. Overview

Web application for Surishi Pharmaceuticals (surishi.in) that replaces a monthly
Excel-driven process for marketing execution: task assignment and tracking,
sales collection vs targets, brand/territory/management performance analytics,
and periodic reporting with PDF export.

## 2. Users & Roles

Nine roles, JWT email+password auth. All demo accounts seeded on backend startup
(see `memory/test_credentials.md`).

| Role | Admin* | User management |
|---|---|---|
| chairman | ✅ | ✅ (exclusive) |
| marketing_head | ✅ | — |
| marketing_deputy_head | ✅ | — |
| product_executive, general_manager, ceo, agm, business_manager, kam | — | — |

*Admin = upload Excel sheets, create/delete tasks. The **CEO** can also create
tasks and upload task sheets (not delete tasks or upload performance sheets).

- **Seniority / task visibility**: chairman > CEO > GM > marketing head = AGM >
  marketing deputy head > business manager > product executive > KAM
  (`ROLE_RANK` in `server.py`). A task assigned to a role (its Role/Assignee
  text, e.g. "GM", "AGM / BM") is hidden from users junior to that role — in
  the task list, task detail, dashboard, reports and filters. Tasks with no
  recognisable role (people, HQs, blank) are visible to everyone; the chairman
  and a task's creator always see it.
- Any user: view visible tasks and performance data, update task status, enter
  collected amounts, attach photos, change own password.
- Chairman only: change any user's role/name/HQ, reset passwords, delete users
  (self-delete blocked), approve/reject new registrations.

### 2.1 Registration approval

New self-service sign-ups no longer auto-activate. `POST /api/auth/register`
creates the account with `status: "pending"` and the requested role, but
returns only a confirmation message — no token. Login is blocked with 403
("pending Admin approval") while `status == "pending"`, and pending accounts
are excluded from `GET /api/users`. The chairman reviews requests on the
Users & Access screen (`GET /api/admin/pending-users`) and either:
- **Approves** (`POST /api/admin/pending-users/{id}/approve`, body
  `{role, hq}`) — the chairman confirms or overrides the requested
  designation before the account is set to `status: "approved"` and can log
  in; or
- **Rejects** (`DELETE /api/admin/pending-users/{id}`) — the pending account
  is deleted outright.

Only the chairman can assign or change a user's designation, either at
approval time or later via the existing `PATCH /api/admin/users/{id}`.
Accounts created before this feature shipped have no `status` field and are
treated as already-approved — the chairman may need to manually correct any
that were self-registered with an unauthorized role, since this system only
prevents that from happening going forward.

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
- **Monthly activity plan upload**: a plan workbook (sheets "DAILY
  COMMUNICATION…", "ACTIVITY PLANNER…", "REQUIREMENT") uploads through the same
  endpoint and becomes tasks: one per day's doctor WhatsApp message (dated),
  one per weekly activity drive (Week N → days 1–7, 8–14, 15–21, 22–end; extra
  blocks span the month; full playbook in the description), and one "Arrange
  inputs" task per requirement section listing per-MR allocations.
- **Replace Task Sheet**: every task carries a `source` (`manual` — created
  in-app — or `sheet` — from an Excel upload or the initial seed). Uploading
  with `POST /api/tasks/upload?replace=true` deletes all existing
  `source: "sheet"` tasks before inserting the new file's rows, so re-uploading
  an updated sheet replaces it instead of appending duplicates; tasks created
  manually in-app (and their status/photos) are never touched. Guarded so a
  file with zero valid rows is rejected with 400 rather than wiping existing
  data. Response includes `replaced_count`. The upload modal on the Tasks
  screen exposes this as a "Replace existing task sheet" checkbox.

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
month's data — idempotent). A month named in a tab's title row (e.g.
"Brand Performance-Sep") takes precedence over the tab name.

**Weekly columns are cumulative month-to-date** ("Sec till 7th", "till 14th",
…). Sales for the month = the sheet's current week (the last week column with
any figures); a row blank in that week counts as 0 there. Achievement % =
that ÷ target — matching the sheets' own Achievement % column. Management
metrics with a blank TOTAL use the latest week.

1. **Brand Performance** — brand, target, W1–W4 sales, computed achievement %,
   top/lowest territory.
2. **Territory Performance** — region → HQ rows with BE/KAM name, DOJ, target,
   weekly secondary sales, achievement %. A region/zone label with no figures
   heads the rows below it; a label with figures ("Total", "Indore Region",
   "All India") is a subtotal and is not stored as a territory.
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
| Auth | `POST /api/auth/register` (pending approval, no token), `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password`, `POST /api/auth/forgot-password` |
| Users | `GET /api/users`, `GET /api/me/features`; chairman: `PATCH /api/admin/users/{id}`, `POST /api/admin/users/{id}/reset-password`, `DELETE /api/admin/users/{id}`, `GET/DELETE /api/admin/reset-requests[/{id}]`, `GET/PUT /api/admin/permissions`, `DELETE /api/admin/data`, `GET /api/admin/pending-users`, `POST /api/admin/pending-users/{id}/approve`, `DELETE /api/admin/pending-users/{id}` |
| Tasks | `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}`, `PATCH /api/tasks/{id}/completion` (per-assignee), `POST /api/tasks/upload?replace=` (replace clears prior sheet-sourced tasks), photos: `POST /api/tasks/{id}/photos`, `DELETE /api/tasks/{id}/photos/{photoId}` |
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
