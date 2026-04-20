# DFB Training Assistant — Project Context
*Last updated: 2026-04-15. Read this at the start of any session on this project.*

---

## What This Is
A RAG-based training chatbot for **Dublin Fire Brigade (DFB)** built as a Proof of Concept. Staff ask questions about training material; Claude Haiku answers using only content from the local knowledge base. No vector DB — manifest-based chunk routing.

**User:** Patrick (patglspy@gmail.com) — non-technical. Needs hand-holding on CLI/deployment. Be patient and step-by-step.

---

## Stack
| Layer | Technology |
|---|---|
| AI model | Claude Haiku (`claude-haiku-4-5-20251001`) via Anthropic API |
| Backend | Python 3 + Flask + Flask-CORS |
| Frontend | Single-file HTML/JS (dark theme, DFB red, mobile-first) |
| Production server | Gunicorn |
| Hosting | Render.com (free tier) — `https://dfb-app.onrender.com` |
| Keep-alive | UptimeRobot pings `/health` every 14 min (free tier spins down after 15 min inactivity) |
| Repo | `github.com/paddums/dfb-app` |
| Local launcher | `START DFB App.command` (double-click on Mac) |

---

## File Structure (DFB app folder)
```
DFB app/
├── app.py                    # Flask backend — RAG logic + API endpoints
├── index.html                # Frontend UI
├── requirements.txt          # anthropic, flask, flask-cors, gunicorn
├── render.yaml               # Render.com deployment config
├── START DFB App.command     # Mac double-click launcher (runs app.py locally)
├── .env                      # ANTHROPIC_API_KEY (never commit this)
├── .gitignore                # Excludes .env, .DS_Store, __pycache__, *.pdf, *.pyc
├── PROJECT_CONTEXT.md        # This file
├── knowledge/                # 29 markdown chunks + manifest.json
│   ├── manifest.json         # 1-sentence summaries for all 29 chunks
│   ├── 01_scba_equipment.md
│   ├── ...
│   └── 29_water_rescue_specialist_operations.md
└── reference_pdfs/           # Source PDFs — local only, not in GitHub
    ├── Recruit BA student notes.pdf
    ├── RTC Student Manual 2025.pdf
    ├── LUKAS eWXT.pdf
    ├── DFB CAFS Course.pdf
    ├── Pump Manual V 7.1.pdf
    └── Water-and-Flood-Rescue-Manual-v21.0.pdf
```

---

## Knowledge Base — 29 Chunks, 6 Source PDFs

| # | File | Source | Topic |
|---|---|---|---|
| 01 | scba_equipment | Recruit BA student notes.pdf (101p) | Scott ProPak-fx SCBA specs |
| 02 | ancillary_equipment | same | Torches, Bodyguard PDSU, TETRA radio, Drager hood |
| 03 | physiology_and_cylinder_duration | same | Respiration physiology + cylinder duration formulas |
| 04 | ba_search_procedures | same | BA search, casualty handling, lost in smoke |
| 05 | compartment_fire_behaviour | same | Fire science, flashover, backdraught, FGI, gas cooling |
| 06 | ventilation_and_ppv | same | Ventilation methods, PPV — offensive PPV banned DFB 2024 |
| 07 | rtc_introduction_and_fire_service_role | RTC Student Manual 2025.pdf (124p) | RTC philosophy, legislation, DFB/Garda/HSE roles |
| 08 | rtc_equipment | same | Holmatro, Lukas tools, Tirfor winch, lifting mats |
| 09 | vehicle_construction | same | Car construction, SRS, airbags, electrics |
| 10 | alternative_fuel_vehicles | same | EV/HV/LPG/Hydrogen hazards at RTC |
| 11 | heavy_goods_vehicles | same | HGV, buses, refrigerated vehicles |
| 12 | agricultural_and_heavy_machinery | same | Tractors, forklifts, tyre explosion hazards |
| 13 | rtc_procedures | same | Scene management, appraisal, motorway incidents |
| 14 | rescue_and_extrication_techniques | same | Roof removal, dash roll, B-post rip, stabilisation |
| 15 | lukas_ewxt_battery_tools | LUKAS eWXT.pdf (21p) | LUKAS SP555 spreaders, S378 cutters, 521 rams |
| 16 | cafs_fundamentals_foam_branches | DFB CAFS Course.pdf (137p) | CAFS intro, Class B foam 3%/6%, Dublin Tunnel overview |
| 17 | cafs_dn14a1_pump_operations | same | DN14A1 (2021) pump bay, Smart CAFS 100 |
| 18 | cafs_dn14a5_operations | same | DN14A5 Reserve + DN15A5R operator guides |
| 19 | cafs_dn14a5_2019_and_smart_cafs | same | DN14A5 2019 Smart CAFS 200, DN14A5 191D, Delta Attack lance |
| 20 | pump_hydraulics | Pump Manual V 7.1.pdf (191p) | Hydraulics fundamentals, friction loss, jet reaction |
| 21 | pump_types | same | Positive displacement, ejector, centrifugal, Prima pumps |
| 22 | pump_gauges_meters_branches | same | Gauges, flow meters, branches, monitors |
| 23 | pump_practical_operations_relays | same | Practical ops, water relays, RTPP foam |
| 24 | pump_cafs_foam_portable_water_supplies | same | CAFS/foam from pump perspective, portable pumps, hydrants |
| 25 | water_rescue_principles_hydrology_flooding | Water-and-Flood-Rescue-Manual-v21.0.pdf (217p) | Rescue 3 philosophy, hydrology, flood theory |
| 26 | water_rescue_medical_and_equipment | same | Drowning, hypothermia, CPR, knots, anchors, mechanical advantage |
| 27 | water_rescue_techniques | same | Swiftwater swimming, tethered rescue, strainer, throw bag |
| 28 | water_rescue_boats_and_incident_management | same | Paddle/tethered boats, boat wraps, incident management |
| 29 | water_rescue_specialist_operations | same | Night ops, weirs, vehicles in water, helicopter familiarisation |

**Notes on knowledge base:**
- Pages 37–38 of BA PDF are image-only (physiology diagrams) — no extractable text, flagged in chunk 03
- All safety-critical lines are wrapped in `> ⚠️ SAFETY — Action > Condition > Standard` blockquotes
- DFB Standard Check active: keywords trigger flagging (Warning, Danger, flashover, backdraught, EV, MAYDAY etc.)

---

## RAG Architecture
- **Routing:** Keyword scoring against manifest summaries + topic hint dictionary (no vector DB)
- **Context window:** Top 2 chunks injected per query (~8,000 input tokens avg)
- **Cost:** ~$0.007–0.013 per query (Haiku pricing). 30 people × 10 questions ≈ $2.50
- **System prompt:** Answers strictly from provided material; surfaces ⚠️ content prominently
- **Endpoints:**
  - `GET /` — serves index.html
  - `POST /ask` — main RAG query endpoint
  - `GET /health` — returns `{"status": "ok"}` (used by UptimeRobot)

---

## Known Issues & Fixes Applied

### Knowledge path on Render
**Problem:** GitHub upload put all .md files at repo root instead of `knowledge/` subfolder.
**Fix in app.py:**
```python
_knowledge_sub = BASE_DIR / "knowledge"
KNOWLEDGE = _knowledge_sub if _knowledge_sub.exists() else BASE_DIR
```
This handles both local (subfolder) and flat (root) layouts.

### Port 5000 blocked on Mac
**Problem:** macOS AirPlay Receiver uses port 5000.
**Fix:** App runs on port **5001** locally.

### Render free tier cold starts
**Problem:** App sleeps after 15 min, 30-50s wake-up delay.
**Fix:** UptimeRobot pings `/health` every 14 minutes.

### `dirname` not found in .command script
**Problem:** First version of launcher failed on Mac.
**Fix:** Use `"$(dirname "${BASH_SOURCE[0]}")"` and explicit PATH with Homebrew locations.

---

## Deployment Workflow
When knowledge base changes (new PDFs added):
1. Process PDFs → new .md files in `knowledge/` folder (use existing chunking pattern)
2. Update `manifest.json` with new chunk summaries
3. Upload new .md files + updated `manifest.json` to GitHub (`github.com/paddums/dfb-app`)
4. Render auto-redeploys on commit (or trigger manual deploy)
5. Update topic hints in `app.py`'s `TOPIC_HINTS` dict for new subjects

When app.py changes:
- Edit directly in GitHub web UI, commit → Render auto-redeploys

---

## API Key
- Stored in `.env` locally: `ANTHROPIC_API_KEY=sk-ant-...`
- Stored as environment variable in Render dashboard
- Never committed to GitHub (.gitignore excludes .env)
- Patrick's personal key — suggest moving to organisational key for wider rollout
- Spend limit should be set at platform.claude.com/settings/limits (suggest $10/month cap)

---

## Topic Hints Dictionary (in app.py)
The `TOPIC_HINTS` dict maps keywords → chunk ID prefixes. When adding new PDFs, add entries for the new subject matter. Current gaps to be aware of: CAFS, pump, water rescue topics need hints added to `app.py` for the 15 new chunks (16–29). Do this before the next deploy.

---

## What's Left / Possible Next Steps
- [ ] Add topic hints to app.py for chunks 15–29 (LUKAS, CAFS, Pump, Water Rescue)
- [ ] Fix GitHub structure: move .md files into `knowledge/` subfolder properly
- [ ] Consider adding a `/topics` endpoint to serve dynamic starter chips from manifest
- [ ] Add conversation history (multi-turn context) if users want follow-up questions
- [ ] Move to organisational Anthropic API key when rolling out beyond PoC
- [ ] Consider Render paid tier ($7/month) for always-on if PoC is approved
- [ ] Add more PDFs as they become available (same chunking pattern applies)
