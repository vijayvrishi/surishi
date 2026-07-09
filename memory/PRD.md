# PRD — Surishi Pharmaceuticals Marketing Execution App

## Original Problem Statement
Mobile app for Surishi Pharmaceuticals (surishi.in) for marketing execution. Every month an Excel is uploaded to update tasks with timelines, assignee, roles & responsibilities. Tasks are daily/weekly and HQ-wise. Task sheet also includes sales collection & targets with reporting due dates. Analysis reports week/month/quarter wise. Users: marketing head, marketing deputy head, product executives, general manager, CEO, chairman, AGM, business manager.

## User Choices
- Excel upload by admin + manual task creation in app
- Standard Excel columns (Task Name, Description, Assignee, Role, HQ, Frequency, Start/Due Date + Category, Target Amount, Reporting Due Date)
- Simple email+password login with role selection (JWT)
- Reports: charts + drill-down lists
- Clean corporate pharma blue/white look (gold accents from Surishi logo)

## Architecture
- Backend: FastAPI + MongoDB (motor), JWT (pyjwt) + argon2 (pwdlib), openpyxl Excel parsing. All routes under /api.
- Frontend: Expo Router (tabs: Dashboard/Tasks/Reports/Profile), react-native-gifted-charts, react-native-keyboard-controller, expo-document-picker. Token in SecureStore via @/src/utils/storage.
- Admin roles: marketing_head, marketing_deputy_head, chairman (upload Excel, create/delete tasks). Chairman additionally has exclusive user management. All 8 roles seeded — see /app/memory/test_credentials.md (password Surishi@123).

## Implemented (Jul 2026 — MVP)
- JWT auth: login/register with role picker, seeded 8 demo accounts
- Excel upload (.xlsx) with flexible header matching → bulk task creation; skipped-row report; admin-only (403 otherwise)
- Task CRUD: filters (Daily/Weekly, status chips, HQ, category, search, period), task detail with status update + collected amount for sales items, admin delete
- Dashboard: monthly KPIs (total/completed/in-progress/overdue), sales collection vs target progress, today's focus, recent tasks, admin quick actions
- Reports: Week/Month/Quarter with donut status chart, sales vs target, By HQ / Assignee / Role completion rows with drill-down task list modal
- Profile: user info, admin shortcuts, logout
- Testing: 21/21 backend tests + full frontend flows passed (iteration_1)

## Implemented (Jul 2026 — Iteration 2)
- Chairman promoted to full admin + exclusive User Management screen (change roles, reset passwords, delete users; self-delete blocked)
- Self-service Change Password (Profile → Change Password) for all users
- PDF report download (reportlab): GET /api/reports/pdf?period=..., Reports tab "PDF" button (web blob download / native share sheet via expo-file-system + expo-sharing)
- Testing: 38/38 backend + all frontend flows passed (iteration_2)

## Implemented (Jul 2026 — Iteration 3: Performance Module)
- Auto-detecting performance Excel upload (POST /api/performance/upload): supports user's 3 real formats — Brand Performance (Brand, Target, Sales W1–W4, Top/Low Territory), Territory Performance (Region → HQ rows with BE/KAM name, DOJ, Target, weekly Sec sales, Achievement %), Management Dashboard (Primary/Secondary sales, Run Rate, Active Doctors, New Prescribers, weekly Top/Lowest Brand & Strong/Weak Territory)
- Parses ALL month sheets in one workbook (Mar–Jun verified); re-upload replaces that month's data (idempotent)
- New Performance tab: month chips + Brands / Territories / Management views with W1–W4 trend bars, achievement badges, region grouping, weekly highlights table
- Upload screen: two buttons — Task Sheet (blue) + Performance Sheet (gold)
- APIs: GET /api/performance/months|brands|territories|management
- Testing: 50/50 backend + frontend passed (iteration_3; upload screen bug found by tester was fixed & verified)

## Implemented (Jul 2026 — Iteration 4)
- Brand-wise MoM Growth view (Performance → Growth): month bars Mar–Jun, per-month growth %, overall growth badge; GET /api/performance/growth
- PDF report now includes performance data: brand table, MoM growth table, territory region summary, management KPIs (latest month)
- Activity photos on tasks: camera/gallery (expo-image-picker, base64 ≤4MB, max 10/task), thumbnails + fullscreen viewer + delete, photo_count pill on cards, full permission flow (canAskAgain + Open Settings), app.json iOS/Android permissions
- Activity heads segregation: Company / Scientific Inputs / Engagement — Excel "Head" column, create-task segment, tasks filter, detail row, reports "Head" dimension + PDF section, task card head pill
- Testing: 17/17 new backend tests + all frontend flows passed (iteration_4)

## Backlog (prioritized)
- P0: none remaining
- P1: Native date pickers on create-task form; per-assignee "My Tasks" view linking user accounts to Excel assignee names; Excel export of reports
- P2: Overdue reminders; monthly archive/comparison view; multi-sheet Excel support; guard chairman self-demotion; migrate shadow* → boxShadow (web-only warnings)

## Next Tasks
- Gather real monthly Excel from user to verify header mapping against actual format
