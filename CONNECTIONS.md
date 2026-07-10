# Connections & Integrations — Surishi Marketing Execution App

Every external system this app connects to, the exact resource involved, and
where its credentials live. **No secrets are stored in this repo** — actual
values live in AWS SSM Parameter Store or the provider's own console.

## 1. Live URLs

| What | URL |
|---|---|
| App (production) | https://app.surishi.in |
| API base | https://app.surishi.in/api |
| API docs (Swagger) | https://app.surishi.in/docs |
| Company site (separate, untouched) | https://surishi.in |

## 2. Database — MongoDB Atlas

| Item | Value |
|---|---|
| Cluster | `Cluster0` — `cluster0.jdq552k.mongodb.net` |
| Database | `surishi` |
| DB user | `vijayaggarwal91` (password: see Atlas → Database Access) |
| Connection string | `mongodb+srv://<user>:<password>@cluster0.jdq552k.mongodb.net/?appName=Cluster0` |
| Where the app reads it | SSM parameter `/surishi/MONGO_URL` → written to `/opt/surishi/backend/.env` on the server |
| Collections | `users`, `tasks`, `brand_performance`, `territory_performance`, `management_dashboard` |

Managed at https://cloud.mongodb.com. Network Access must allow the EC2
instance's IP (`3.6.111.165`) or `0.0.0.0/0`.

## 3. Hosting — AWS (account 516887748193, region ap-south-1 / Mumbai)

| Resource | ID / Name | Purpose |
|---|---|---|
| EC2 instance | `i-02ed8e2c8fbcb1385` (`surishi-backend`, t3.micro, Amazon Linux 2023) | Runs nginx + FastAPI backend + serves frontend build |
| Elastic IP | `3.6.111.165` (`eipalloc-0e3e272f5baacfc2d`) | Stable public IP the domain points at |
| Security group | `sg-0802301c92be41b54` (`surishi-backend-sg`) | Inbound 80/443 only — **no SSH**; admin access is via SSM |
| IAM role | `surishi-ec2-role` + instance profile `surishi-ec2-profile` | Lets the instance read `/surishi/*` SSM params + be managed by SSM |
| IAM deploy user | `surishi-deploy` | Scoped user used for provisioning/deploys (Amplify/EC2/SSM policies) |
| SSM parameters | `/surishi/MONGO_URL` (SecureString), `/surishi/DB_NAME`, `/surishi/JWT_SECRET` (SecureString) | Runtime secrets for the backend |

On-server layout: code at `/opt/surishi` (git clone of this repo), backend
venv + `.env` in `/opt/surishi/backend`, frontend build served from
`/opt/surishi/frontend/dist`, nginx config at `/etc/nginx/conf.d/surishi.conf`,
backend runs as systemd service `surishi-backend` on `127.0.0.1:8000`.

## 4. DNS — GoDaddy

| Item | Value |
|---|---|
| Domain | `surishi.in` (nameservers `ns13/ns14.domaincontrol.com`) |
| App record | `A` record, host `app` → `3.6.111.165` (TTL 600) |
| Managed at | GoDaddy → surishi.in → Manage DNS |

Do **not** use GoDaddy "Forwarding" for the `app` subdomain — it overrides the
A record and breaks the app (this happened once during setup).

## 5. TLS — Let's Encrypt

| Item | Value |
|---|---|
| Certificate | `app.surishi.in`, issued via certbot (nginx plugin) |
| Renewal | Automatic — `certbot-renew.timer` (systemd, runs daily) |
| Cert files | `/etc/letsencrypt/live/app.surishi.in/` on the instance |
| Registered email | vijay.vihaan91@gmail.com (expiry notices go here) |

## 6. Source code — GitHub

| Item | Value |
|---|---|
| Repo | https://github.com/vijayvrishi/surishi (public) |
| Branch | `main` — the server deploys whatever is on this branch via `git pull` |
| Key docs | `SPEC.md` (full spec), `README.md` (local dev), `backend/openapi.json` (API schema) |

## 7. App-level auth

| Item | Value |
|---|---|
| Mechanism | JWT (HS256), 7-day expiry, signed with `/surishi/JWT_SECRET` |
| Seeded accounts | 8 demo users, password `Surishi@123` — see `memory/test_credentials.md` |
| Admin roles | chairman, marketing_head, marketing_deputy_head |

## 8. How the pieces talk to each other

```
GoDaddy DNS (app.surishi.in → 3.6.111.165)
        │
Browser ─HTTPS (Let's Encrypt)→ nginx on EC2
        ├── /            → static React build
        └── /api, /docs  → uvicorn (FastAPI) on localhost:8000
                                │
                                └─ mongodb+srv (TLS) → MongoDB Atlas
Backend secrets: SSM Parameter Store ─(instance role)→ backend .env at deploy time
Deploys: GitHub main ─(git pull via SSM command)→ /opt/surishi → npm build + service restart
```

## 9. If something breaks — who to check first

| Symptom | Likely place |
|---|---|
| Site unreachable | EC2 instance state / Elastic IP (AWS console) |
| Site loads, API errors / can't log in | Backend service (`journalctl -u surishi-backend`) or Atlas (auth/network access) |
| Certificate warnings | certbot renewal on the instance |
| Domain resolves wrong | GoDaddy DNS records (check no Forwarding rule reappeared) |
