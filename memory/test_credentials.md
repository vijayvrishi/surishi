# Test Credentials — Surishi Pharma Marketing Execution App

All demo accounts are auto-seeded on backend startup.

**Password for ALL accounts: `Surishi@123`**

| Role | Email | Rights |
|---|---|---|
| Chairman | chairman@surishi.in | ✅ FULL: Excel upload, create/delete tasks + USER MANAGEMENT (change roles, reset passwords, delete users) |
| Marketing Head | head@surishi.com | ✅ Admin (Excel upload, create/delete tasks) |
| Marketing Deputy Head | deputy@surishi.com | ✅ Admin (Excel upload, create/delete tasks) |
| Product Executive | pe@surishi.com | Member |
| General Manager | gm@surishi.com | Member |
| CEO | ceo@surishi.com | Member |
| AGM | agm@surishi.com | Member |
| Business Manager | bm@surishi.com | Member |

All users can change their own password: `POST /api/auth/change-password`.
PDF report: `GET /api/reports/pdf?period=week|month|quarter` (Bearer auth).

Auth: JWT Bearer token from `POST /api/auth/login` with `{email, password}`.
