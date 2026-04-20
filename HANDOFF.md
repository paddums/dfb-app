# DFB Training Assistant — Handoff Document
*Written: 2026-04-16. For whoever picks this up next.*

---

## What It Is

A RAG chatbot for Dublin Fire Brigade training. Firefighters type questions; the app finds the right section from the training manuals and asks Claude Haiku to answer — in scannable bullet format, safety-critical info first.

No vector database. Just smart keyword routing against a manifest of chunk summaries.

**Live URL:** https://dfb-app.onrender.com  
**GitHub:** github.com/paddums/dfb-app  
**Local launcher:** Double-click `START DFB App.command` on Mac

---

## Current State (April 2026)

✅ **Working and deployed:**
- 29 knowledge chunks covering 6 source PDFs (BA, RTC, LUKAS, CAFS, Pump Ops, Water Rescue)
- Smart keyword routing via `TOPIC_HINTS` dict in `app.py` — all 29 chunks covered
- Mobile-first dark UI with topic chips and follow-up suggestions
- `/topics` endpoint serving starter questions per topic
- `/health` endpoint kept alive by UptimeRobot every 14 min
- Handles both flat (root) and subfolder (`knowledge/`) GitHub file layouts

✅ **Recently completed:**
- Full `TOPIC_HINTS` coverage for all chunks including LUKAS (15), CAFS (16–19), Pump (20–24), Water Rescue (25–29)
- `ingest.py` for adding future PDFs to the knowledge base without manual chunking

---

## Files That Matter

| File | What It Does |
|---|---|
| `app.py` | **The brain.** Flask backend, RAG routing, Claude API call. Edit TOPIC_HINTS here when new subjects are added. |
| `knowledge/manifest.json` | **The index.** One summary per chunk. Routing scores against these. Keep accurate. |
| `ingest.py` | **The pipeline.** Drop a new PDF → run this → chunk .md + manifest entry written automatically. |
| `index.html` | Frontend UI. Single file, no build step. |
| `render.yaml` | Render.com deployment config. Rarely needs touching. |
| `requirements.txt` | Python dependencies. Add here if ingest.py needs new packages. |

---

## How to Add a New PDF (the right way)

1. Put the PDF in the `reference_pdfs/` folder
2. Run: `python3 ingest.py "reference_pdfs/My New Manual.pdf" --topic "Topic Name"`
3. Script extracts text, writes the `.md` chunk file, updates `manifest.json`, and generates a summary using Claude API
4. Open `app.py` and add relevant keywords to `TOPIC_HINTS` for the new subject
5. Upload the new `.md` file + updated `manifest.json` + `app.py` to GitHub → Render auto-redeploys

---

## Three Ways to Make Changes (simplest first)

### Option A — GitHub Web UI (no git, no server, ~10 min)
*Best for: updating app.py routing, fixing a chunk, tweaking the prompt*

1. Go to **github.com/paddums/dfb-app**
2. Click the file you want to edit (e.g. `app.py`)
3. Click the pencil icon (✏️) top-right
4. Make your changes
5. Click **"Commit changes"** (green button)
6. Render auto-deploys in ~2 minutes

The five files you'd most likely edit this way:
- `app.py` — routing tweaks, system prompt changes
- `knowledge/manifest.json` — update a chunk summary
- `index.html` — UI changes
- `requirements.txt` — add a dependency
- Any `knowledge/XX_chunk_name.md` — fix content in a chunk

### Option B — Git (command line)
*Best for: adding multiple files at once, running ingest.py*

```bash
git clone https://github.com/paddums/dfb-app
cd dfb-app
# make changes / run ingest.py
git add .
git commit -m "Add new manual chunks"
git push
```
Render picks it up automatically on push.

### Option C — Run ingest.py locally, upload outputs manually
*Best for: processing new PDFs without touching git*

1. Run `python3 ingest.py "reference_pdfs/NewManual.pdf" --topic "Subject Name"` locally
2. The script writes `knowledge/30_new_chunk.md` and updates `manifest.json`
3. In GitHub web UI, upload the new `.md` file (drag-and-drop works) and paste the updated `manifest.json`
4. Add keywords to `TOPIC_HINTS` in `app.py` (Option A above)
5. Render redeploys

---

## API Key & Costs

- API key is stored in `.env` locally and as an env var in the Render dashboard
- Never committed to GitHub — `.gitignore` excludes `.env`
- Current key: Patrick's personal key. Move to an organisational key before wider rollout.
- Set a spend cap at: https://platform.claude.com/settings/limits (suggest $10/month)
- Estimated cost: ~$0.01 per query (Haiku pricing). 30 users × 10 questions/day = ~$2.50/month

---

## Known Quirks

| Issue | Fix |
|---|---|
| App slow to respond first time | Render free tier cold start (~30–50s). UptimeRobot keeps it warm every 14 min. |
| Port 5000 blocked locally on Mac | App runs on **port 5001** locally. http://localhost:5001 |
| GitHub uploads land at root, not `knowledge/` | `app.py` checks both locations automatically — works either way |
| Pages 37–38 of BA PDF are images | No text extractable from those pages — flagged in chunk 03 |

---

## If Something Breaks

1. Check https://dashboard.render.com — is the deploy green?
2. Check logs in Render dashboard for Python errors
3. Test the `/health` endpoint: https://dfb-app.onrender.com/health — should return `{"status":"ok"}`
4. If the knowledge base is suspect, re-run `ingest.py` on the relevant PDF
5. API errors? Check the key is set in Render environment variables

---

*Read `PROJECT_CONTEXT.md` for the full technical deep-dive.*
