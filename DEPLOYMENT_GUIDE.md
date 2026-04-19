# ShopWave Agent — Render Deployment Guide

> **Stack:** Python · FastAPI · LangGraph · Google Gemini 2.5 Flash  
> **Target:** [Render.com](https://render.com) Web Service  
> **Start command:** `uvicorn api.server:app --host 0.0.0.0 --port $PORT`

---

## Prerequisites

| Requirement | Notes |
|---|---|
| GitHub account | Project must be pushed to a GitHub repo |
| Render account | Free tier works; paid tier recommended for production |
| Google Gemini API key | Get one at [aistudio.google.com](https://aistudio.google.com) |
| Python 3.11+ | Render auto-detects from your repo |

---

## Step 1 — Push the project to GitHub

If you haven't already:

```bash
cd shopwave-agent
git init                        # skip if .git already exists
git add .
git commit -m "chore: render deployment setup"
git remote add origin https://github.com/YOUR_USERNAME/shopwave-agent.git
git push -u origin main
```

> ⚠️ Make sure `.env` is in `.gitignore` (it already is). Never push your `GEMINI_API_KEY`.

---

## Step 2 — Create a new Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) and click **New → Web Service**
2. Select **Build and deploy from a Git repository**
3. Connect your GitHub account if prompted, then select the `shopwave-agent` repo
4. Click **Connect**

---

## Step 3 — Configure the service

Fill in the fields on the setup page:

| Field | Value |
|---|---|
| **Name** | `shopwave-agent` (or any name you like) |
| **Region** | Closest to your users |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn api.server:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Starter ($7/mo) or Free (spins down after inactivity) |

> Render auto-detects the `Procfile` and `render.yaml` — you can also use **Blueprint** (see Step 3b).

### Step 3b (Optional) — Deploy via Blueprint

If you want Render to auto-configure everything from `render.yaml`:

1. Go to **New → Blueprint**
2. Select your repo
3. Render reads `render.yaml` and pre-fills all settings
4. You still need to add `GEMINI_API_KEY` manually (see Step 4)

---

## Step 4 — Set Environment Variables

In your Render service dashboard go to **Environment** tab and add:

| Key | Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | `your_actual_key_here` | **Required.** Mark as Secret |
| `INJECT_FAULTS` | `false` | Set `true` only for demo/testing |
| `LOG_LEVEL` | `INFO` | Options: `DEBUG`, `INFO`, `WARNING` |
| `MAX_CONCURRENT_TICKETS` | `5` | Semaphore limit for batch processing |
| `MAX_TOOL_RETRIES` | `3` | Retry attempts per tool call |

> 🔒 Click the **eye/lock icon** next to `GEMINI_API_KEY` to mark it as a secret — Render will mask it in logs.

---

## Step 5 — Deploy

Click **Create Web Service**. Render will:

1. Clone your repo
2. Run `pip install -r requirements.txt`
3. Start `uvicorn api.server:app --host 0.0.0.0 --port $PORT`

Watch the **Logs** tab — a successful startup looks like:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000
```

Your service URL will be:
```
https://shopwave-agent.onrender.com
```

---

## Step 6 — Verify the deployment

### Health check
```bash
curl https://shopwave-agent.onrender.com/health
```
Expected:
```json
{"status": "ok", "version": "1.0.0"}
```

### Interactive API docs
Open in your browser:
```
https://shopwave-agent.onrender.com/docs
```

### Process a single ticket
```bash
curl -X POST https://shopwave-agent.onrender.com/tickets/process \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "ticket_id": "TKT-001",
      "customer_email": "alice.turner@email.com",
      "subject": "Headphones stopped working",
      "body": "My order ORD-1001 headphones broke after 2 weeks.",
      "order_id": "ORD-1001"
    }
  }'
```

### Process a batch
```bash
curl -X POST https://shopwave-agent.onrender.com/tickets/batch \
  -H "Content-Type: application/json" \
  -d '{
    "tickets": [
      {"ticket_id": "TKT-001", "customer_email": "alice.turner@email.com", "subject": "Refund request", "body": "I want a refund for ORD-1001", "order_id": "ORD-1001"},
      {"ticket_id": "TKT-002", "customer_email": "bob.smith@email.com", "subject": "Order status", "body": "Where is my order ORD-1002?", "order_id": "ORD-1002"}
    ]
  }'
```

### Get the audit log
```bash
curl https://shopwave-agent.onrender.com/audit-log
```

### Get status of a specific ticket
```bash
curl https://shopwave-agent.onrender.com/tickets/TKT-001/status
```

---

## Important: Render filesystem behaviour

Render web services use an **ephemeral filesystem** — any files written to disk (including `audit_log.json`) are:

- ✅ Written successfully during the service's runtime
- ❌ **Lost on every deploy or restart**

This means `audit_log.json` will reset on each new deploy. This is fine for demo/testing purposes. If you need persistent audit logs in production, options are:

1. **Render Disk** — Add a persistent disk in the Render dashboard (paid plans), mount it at `/data`, and update `AUDIT_LOG_PATH` in `main.py` and `api/server.py` to `Path("/data/audit_log.json")`
2. **External storage** — Write logs to a database (Supabase, PlanetScale) or object storage (S3, Cloudflare R2)

---

## Auto-Deploy on Git Push

By default Render enables **auto-deploy** — every push to `main` triggers a new deploy. To change this:

- Go to **Settings → Build & Deploy → Auto-Deploy** and toggle it off for manual control

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `500` on all endpoints | `GEMINI_API_KEY` missing or wrong | Check Environment tab in Render dashboard |
| Service won't start | Import error on boot | Check Render logs — usually a missing package |
| `ModuleNotFoundError: google.genai` | pip install didn't run | Verify Build Command is set correctly |
| Tickets return `resolution: failed` | Gemini API quota exceeded | Check Google AI Studio quota |
| Free tier times out | Render spins down free services after 15 min inactivity | First request after sleep takes ~30s; upgrade to Starter to avoid this |
| `audit_log.json` empty after restart | Ephemeral filesystem | Expected — see filesystem note above |

---

## API Reference Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check — use for Render health check config |
| `POST` | `/tickets/process` | Process one ticket through the full LangGraph pipeline |
| `POST` | `/tickets/batch` | Process multiple tickets concurrently (Semaphore 5) |
| `GET` | `/audit-log` | Full audit log (resets on redeploy) |
| `GET` | `/tickets/{ticket_id}/status` | Status of a specific processed ticket |
| `GET` | `/docs` | Swagger UI — interactive API docs |
| `GET` | `/redoc` | ReDoc — alternative API docs |

---

## Environment Variables Reference

| Variable | Default | Required | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | — | ✅ Yes | Google Gemini API key |
| `INJECT_FAULTS` | `true` | No | Enable simulated tool failures |
| `LOG_LEVEL` | `INFO` | No | Logging level |
| `MAX_CONCURRENT_TICKETS` | `5` | No | asyncio Semaphore limit |
| `MAX_TOOL_RETRIES` | `3` | No | Retry attempts per tool |
| `PORT` | — | Auto | Set automatically by Render — do not override |
