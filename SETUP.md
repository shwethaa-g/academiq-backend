# AcademIQ Backend — Complete Setup Guide

## What's in this backend

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI entry point, CORS, all routers mounted |
| `app/core/config.py` | All env vars via pydantic-settings |
| `app/core/security.py` | JWT create/decode, `get_current_user`, role guards |
| `app/db/supabase.py` | Supabase client singleton (service role key) |
| `app/models/schemas.py` | All Pydantic models |
| `app/services/risk_engine.py` | 6-signal weighted scoring, tier logic |
| `app/services/sentiment.py` | Claude API sentiment + rule-based fallback |
| `app/services/alerts_service.py` | Resend — RED immediate + AMBER daily digest |
| `app/routers/auth.py` | Login/logout, demo credentials, JWT issuance |
| `app/routers/students.py` | List, filter, paginate, profile + trends |
| `app/routers/alerts.py` | List, action (logs intervention), stats |
| `app/routers/surveys.py` | Submit survey → Claude analysis → risk rescore |
| `app/routers/reports.py` | Admin stats, mentor stats, cohort trends, alert volume |
| `app/routers/mentors.py` | List mentors, mentor's students |
| `app/routers/risk.py` | Manual + bulk risk recomputation, alert creation |
| `scripts/schema.sql` | Full Supabase schema — all tables, indexes, RLS |
| `scripts/seed.py` | 50 students, 12 weeks data, pre-seeded RED/AMBER trajectories |

---

## Step 1 — Virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

---

## Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in every value:

| Variable | Where to get it |
|---|---|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → `service_role` key |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `RESEND_API_KEY` | resend.com → API Keys |
| `RESEND_FROM_EMAIL` | A domain you've verified in Resend |
| `ALLOWED_ORIGINS` | Your Vercel URL + `http://localhost:5173` |

---

## Step 4 — Run the schema on Supabase

**Option A — Supabase Dashboard (recommended):**
1. Go to your project → **SQL Editor → New query**
2. Paste the full contents of `scripts/schema.sql`
3. Click **Run**

**Option B — psql CLI:**
```bash
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f scripts/schema.sql
```

---

## Step 5 — Seed the database

```bash
python scripts/seed.py
```

This creates:
- 3 mentors
- 50 students (8 RED, 14 AMBER, 28 GREEN)
- 12 weeks of attendance, grade, engagement, sentiment data
- Alerts and intervention logs
- Cohort weekly snapshots

---

## Step 6 — Start the dev server

```bash
uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|---|---|
| `http://localhost:8000` | API root |
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/health` | Health check |

---

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@academiq.demo` | `admin123` |
| Mentor | `mentor@academiq.demo` | `mentor123` |
| Student | `student@academiq.demo` | `student123` |

Login endpoint: `POST /auth/login` (form-encoded, not JSON)

---

## Deploy to Railway

### 1. Install Railway CLI and login
```bash
npm install -g @railway/cli
railway login
```

### 2. Create project
```bash
railway init
```

### 3. Set environment variables
```bash
railway variables set SECRET_KEY="..."
railway variables set SUPABASE_URL="..."
railway variables set SUPABASE_SERVICE_ROLE_KEY="..."
railway variables set ANTHROPIC_API_KEY="..."
railway variables set RESEND_API_KEY="..."
railway variables set RESEND_FROM_EMAIL="..."
railway variables set ALLOWED_ORIGINS="https://your-app.vercel.app"
railway variables set APP_ENV="production"
```

Or paste them all in Railway Dashboard → your service → **Variables** tab.

### 4. Deploy
```bash
railway up
```

Railway reads `Procfile` automatically:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 5. Get your URL
```bash
railway domain
```

---

## Wire up the frontend

In Vercel → your project → **Settings → Environment Variables**:

```
VITE_API_URL = https://your-railway-app.up.railway.app
```

Redeploy the frontend. Done.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
Run uvicorn from the project root — the folder that *contains* the `app/` directory.

**Supabase 403 errors**
Make sure you're using the `service_role` key, not the `anon` key.

**CORS errors from frontend**
`ALLOWED_ORIGINS` must exactly match your Vercel URL with no trailing slash.

**`422 Unprocessable Entity` on login**
The `/auth/login` endpoint expects `application/x-www-form-urlencoded` (OAuth2 form), not JSON.

**Emails not arriving**
Verify your sender domain in Resend dashboard. Check spam folders.
