# ShopWave Agent — React Demo App
# Vercel Deployment Guide

## What's inside

`demo-app/` is a self-contained **Vite + React** single-page app that showcases the ShopWave Agent project for hackathon judges. It contains:

- **Overview** — hero, resolution stats, key metrics
- **Architecture** — interactive 6-node LangGraph diagram
- **Ticket Audit Log** — filterable/searchable table of all 20 tickets
- **Tool Palette** — 9 async tools + key design decisions
- **API Reference** — endpoints + curl/Python/JSON code examples

All data is static (mirrors the actual `audit_log.json` output) — no backend needed.

---

## Local development

```bash
cd demo-app
npm install
npm run dev
```

Open http://localhost:5173

---

## Deploy to Vercel (fastest path)

### Option A — Vercel CLI (recommended, ~2 minutes)

```bash
# 1. Install Vercel CLI globally (once)
npm install -g vercel

# 2. Move into the demo-app directory
cd demo-app

# 3. Install dependencies
npm install

# 4. Deploy
vercel

# Follow the prompts:
#   Set up and deploy? → Y
#   Which scope? → (your account)
#   Link to existing project? → N
#   Project name → shopwave-agent-demo (or anything)
#   In which directory is your code? → ./   (you're already inside demo-app)
#   Want to modify settings? → N
#
# Vercel auto-detects Vite and sets:
#   Build Command:  npm run build
#   Output Dir:     dist
#   Install Cmd:    npm install
```

Your live URL will be printed immediately, e.g.:
`https://shopwave-agent-demo.vercel.app`

**Subsequent deploys:**
```bash
vercel --prod
```

---

### Option B — Vercel Dashboard (no CLI)

1. Push the **entire `shopwave-agent` repo** to GitHub (or just the `demo-app/` folder).
2. Go to https://vercel.com/new → **Import Git Repository**.
3. Select your repo.
4. In **Configure Project**, set:
   - **Root Directory:** `demo-app`
   - **Framework Preset:** Vite *(auto-detected)*
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. Click **Deploy**.

Done — Vercel gives you a shareable URL instantly.

---

### Option C — Drag & Drop (zero config, instant)

```bash
cd demo-app
npm install
npm run build
```

Then go to https://vercel.com/new → **Deploy without Git** → drag the `demo-app/dist` folder into the upload area.

Live in under 30 seconds. No account setup required for the first deploy.

---

## Environment variables

None required — the demo app is fully static with no API calls.

---

## Project structure

```
demo-app/
├── index.html          # Entry HTML (Google Fonts loaded here)
├── vite.config.js      # Vite config with @vitejs/plugin-react
├── package.json
├── public/
│   └── favicon.svg
└── src/
    ├── main.jsx        # React root
    ├── index.css       # Global styles + CSS variables + animations
    ├── App.css         # App-level (minimal)
    └── App.jsx         # Entire single-page app (all sections)
```

---

## Recording the demo video

Suggested flow (5–7 min):

1. **Open the live Vercel URL** in full-screen browser (1920×1080 recommended).
2. **Overview section** — point out resolution breakdown (14 resolved / 4 escalated / 2 clarify), stats row, tech stack tags.
3. **Architecture section** — click each node to expand the description. Highlight the social-engineering bypass arrow.
4. **Ticket Audit Log** — filter by "escalated", then search "TKT-005" to show the social-engineering ticket detail panel. Then search "alice" to pull up TKT-001 (VIP).
5. **Tool Palette** — walk through lookup vs action tools. Point out the 4 key design decisions (confidence scoring, refund guard, social-engineering pre-routing, dead-letter queue).
6. **API Reference** — switch between curl / python / response tabs. Mention `http://localhost:8000/docs` for Swagger UI.
7. **(Optional) Terminal** — show `python main.py` running with live progress output alongside the app.

Tips:
- Use a screen recorder like OBS, Loom, or QuickTime.
- Keep browser zoom at 100% — the neo-brutalist design is crisp at native resolution.
- The yellow ticker bar at the top is a good visual anchor — start and end shots there.

---

## Customisation

To update ticket data with a new `audit_log.json` run, edit the `TICKETS` array at the top of `src/App.jsx`. Each entry needs:

```js
{
  id, email, subject, category, urgency,
  resolution,   // 'resolved' | 'escalated' | 'clarify' | 'failed'
  confidence,   // 0.0 – 1.0
  tools,        // number of tool calls
  ms,           // processing time in milliseconds
  tier,         // 'vip' | 'premium' | 'standard'
  order,        // order ID string or null
}
```
