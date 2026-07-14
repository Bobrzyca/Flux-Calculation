# Flux Calculation

**One-line description:** A local tool that ingests raw closed-chamber greenhouse-gas measurement files, auto-matches them by timestamp, and computes CO₂ and CH₄ flux (per m², per second, and across a full unit ladder) for each measurement spot.

## Problem it solves
Greenhouse-gas flux measurement produces several files from different instruments that must be stitched together by time before any flux can be calculated: a continuous 1 Hz concentration log, hand-typed start/stop times per spot, a separate temperature log, and pressure data. Today this is done with an R script that relies on manual timestamp alignment, hard-coded paths, and a fake pressure value — slow, error-prone, and hard to supervise. Flux Calculation automates the matching and the math while keeping every transformation visible.

## Target user
The author and research friends doing similar closed-chamber GHG work — same instrument family (LI-7810), mostly the same file formats, but each bringing their own field data. Not a public product; a shared personal/lab tool each person runs locally.

## How it differs from existing solutions
It automatically matches four separate field files by timestamp (with a correctable instrument clock offset), tolerates the messy human formatting of hand-typed field notes via an LLM parser, and exposes every processing step for supervision — instead of babysitting an R script and aligning timestamps by hand.

## MVP features
1. **Import the four sources** — LI-7810 concentration, time-window notes, temperature xlsx, IMGW pressure; chamber constants as config. Tolerant parsing so friends' files also work.
2. **Time-shift correction** — apply an offset (seconds) to the LI-7810 timestamps before matching, because the instrument clock drifts from real time.
3. **Auto-match by timestamp** — slice the continuous concentration stream into per-spot windows from the notes; attach the correct temperature and pressure to each. *The core.*
4. **Fit slope + compute flux** — linear regression of concentration vs. time per gas per spot (with R² per gas), then the closed-chamber flux formula → flux per m²·s and the full unit ladder. Pure code, no LLM.
5. **Results + per-spot supervision + export** — a results table (with anomaly/low-R² flags), a per-spot detail view showing the concentration points and the fitted regression line, a campaign-wide processing log, and save/download to Excel or txt.

## Out of scope for MVP
- Cross-campaign comparison and season-long dashboards inside the app (handled at the n8n layer instead, on a single-campaign basis).
- Map view of measurement spots.
- Non-linear / exponential flux fitting (linear only in v1).
- Automatic time-shift *detection* (v1: the user enters the offset).
- Multi-user accounts / login / sharing (local tool).
- Automatically fetching IMGW pressure (the user uploads it themselves).

## Repository structure
- `frontend/` — user interface (React + Vite + Tailwind + Plotly)
- `backend/` — server logic, parsing, matching, flux math, API (Python + FastAPI)
- `reference/` — the original R script, cleaned to run on sample files; the method-of-record for validation (see "R script as reference" below)

## Tech stack
- **Frontend:** React + Vite + Tailwind, built with the coding agent; Plotly for the per-spot regression plot (zoom/pan to inspect fits).
- **Backend framework:** Python + FastAPI. `pandas` for wrangling, `numpy` / `scipy` (`scipy.stats.linregress`) for slope + R², `openpyxl` for xlsx, `python-docx` for Word notes.
- **Database:** SQLite (one file, zero setup, travels with the analysis).
- **Other libraries / APIs:** An LLM SDK (Python) in JSON/structured-output mode for the notes/pressure parser and the n8n quality-check step. n8n for the AI quality-check workflow.

## Screens / pages
1. **Upload / New analysis** — upload the four files; set chamber constants (pre-filled area 0.0625 m², volume 15.625 L) and time-offset (default 0); name the analysis; Run.
2. **Confirm parsed notes** — the LLM-parsed time-notes shown as an editable table for review before matching; flags blank GPS and oddities; approve to proceed.
3. **Results table** — all spots with fluxes, GPS, light/dark, R² per gas, and quality flags; sort/filter; save/download (Excel or txt).
4. **Per-spot detail** — concentration points with the fitted regression line drawn through them (per gas), plus the exact temperature/pressure/offset/rows used and the fit window.
5. **Processing log** — campaign-wide audit trail of every transformation (rows dropped, offset applied, which pressure matched to which spot, warnings).

## Navigation
A stepper bar across the top (Upload → Confirm → Results) that shows the current stage and lets the user click back to a previous step. Per-spot detail and processing log open from the results screen.

## Branding
- **App display name:** Flux Calculation
- **Logo:** simple flat mark (a gas-bubble or chamber motif); minimal, scientific.
- **Tone of voice:** friendly but precise — a competent field colleague. Plain sentences, no jargon in the UI.
- **Slogan (optional):** "From messy field notes to clean fluxes"

## Colour scheme
- **Primary:** `#0F766E` — deep teal (wetland water, calm, scientific)
- **Secondary:** `#92400E` — warm brown (wood, dam, earthy)
- **Background:** `#F8FAFC` — near-white (clean data tables)
- **Text:** `#1E293B` — slate (soft near-black)
- **Accent / CTA:** `#F59E0B` — amber (the "Run analysis" button)
- **Style:** clean, scientific, uncluttered — data-first, like a modern lab tool, not corporate SaaS.

## Typical user flow
1. The user opens the app and sees their saved analyses (or, on first run, a prompt to upload files).
2. They start a new analysis and upload the four files, confirm chamber constants, and set the time-offset if the LI-7810 clock was off.
3. They click Run; the LLM parses the messy field notes into a clean table.
4. They review and edit the parsed notes on the Confirm screen, then approve.
5. The system matches temperature and pressure to each spot, fits CO₂ and CH₄ slopes over the 30 s + 5 min window, computes flux, and runs the n8n quality check.
6. The user sees the results table with fluxes, R² per gas, and anomaly/low-R² flags; clicks any spot to inspect its regression plot; and saves/downloads the results to Excel or txt.

## Authentication and users
- **Login required:** no
- **Login method:** none (local tool)
- **User roles:** none (single role — the person running it)
- **What a logged-out visitor sees:** n/a; the app opens straight to the saved-analyses / upload screen.

## Data entered by the user
- Four uploaded files: LI-7810 concentration txt, time-window notes (Word/Excel/CSV), temperature xlsx, IMGW pressure (format may vary).
- Chamber constants: area (default 0.0625 m²) and volume (default 15.625 L).
- Time-shift offset in seconds (default 0).
- Analysis name and work date.
- Edits/confirmation of the LLM-parsed notes table.

## Data stored by the application
- `Analysis(id, name, work_date, chamber_area_m2, chamber_volume_l, time_offset_seconds, created_at)`
- `Spot(id, analysis_id, nr, gps, light_dark, location_desc, start_time, stop_time)`
- `Reading(id, spot_id, timestamp, co2_ppm, ch4_ppb, temperature_used, pressure_used)`
- `FluxResult(id, spot_id, gas, slope, r2, flux_umol_m2_s, flux_umol_m2_h, flux_mol_m2_h, flux_gC_m2_day, flux_kg_m2_h, flux_kg_ha_h, flux_kg_ha_day, flux_kg_ha_year, flux_Mg_ha_year, flux_Mg_ha_year_co2equiv, n_points)`
- Raw uploaded files are also saved on disk and referenced by the Analysis, so any campaign can be re-run.

## External data sources
- **LLM API** — for parsing the messy field notes and the unknown-format pressure file into clean JSON, and for the n8n quality-check step.
- **n8n** — receives results and returns a quality report.
- No live/third-party data feeds; IMGW pressure is uploaded by the user, not fetched.

## Output format for the user
On-screen results table (per spot, both gases) with quality flags, an interactive per-spot regression plot, a processing log, and downloadable results in **Excel (.xlsx)** or **tab-delimited txt**. *(CSV as a possible third format — assumption, confirm before building.)* Results-table columns: `Nr, date, start, stop, GPS, light/dark, location, CO₂ flux, CH₄ flux, R²_CO2, R²_CH4, temperature used, pressure used, time-offset applied` plus the full unit ladder in the export.

## Error states
- **Invalid user input:** show the exact file and row (e.g. "Row 13 in the time notes: stop 13:33 is before start 13:27"). A bad row skips that spot and flags it in the results and log, so one messy row never blocks the others.
- **External API failure:** if the LLM parser times out or returns invalid JSON, fall back to a hand-editable table with a banner ("Automatic parsing failed — please check the times below manually"); the pipeline never dead-ends. If the n8n quality check is unavailable, results still show with a "quality check unavailable" note.
- **Empty state (no data):** friendly prompt with the upload button ("No analyses yet. Upload your LI-7810, time notes, temperature and pressure files to calculate your first fluxes."), never a blank page.
- **Slow loading:** live step indicator ("Parsing notes… matching temperature… fitting CO₂ and CH₄… done") so the pipeline is visibly working, never a frozen screen.

## Handling of `nan` and warm-up (LI-7810)
- Skip any row where CO₂ or CH₄ is `nan`; do not crash (matches the R script behaviour).
- The instrument warm-up period at the start of the file (all `nan` while the laser stabilises) is expected and silent — no warning.
- `nan` rows *inside* an actual measurement window are dropped but reported in the processing log and per-spot view (e.g. "Spot 7: 12 of 300 readings dropped (nan)").

## Smart features (LLM via API)

### Smart feature 1: Field-notes parser
- **What it does:** Converts the messy, hand-typed time-window notes (and the unknown-format IMGW pressure file) into clean, strict JSON the pipeline can trust — tolerating dot-separated times (`9.38`), redo markers (`3!`), stray spaces (`13 33`), blank/`?` GPS, and Polish column headers.
- **Input:** The uploaded notes file (Word/Excel/CSV) and the pressure file (format may vary). Text/table content extracted server-side and sent to the LLM.
- **Output:** JSON — for notes: `[{nr, start_time, stop_time, gps, light_dark, location}]`; for pressure: `[{timestamp, pressure_hPa}]`. Validated server-side (times parse; stop > start) before use.
- **Where it lives:** Triggered on Run (Upload screen); the parsed notes are shown on the Confirm screen for review/edit before matching.
- **Model and why:** A cheap, fast, capable model in structured/JSON output mode — this is format normalisation, not deep reasoning.
- **Prompt strategy:** System prompt defining the target schema, plus few-shot examples of messy → clean; JSON output mode enforced.
- **Failure handling:** Timeout or invalid JSON → retry once, then fall back to a hand-editable table with a warning banner. Server-side validation rejects impossible times and surfaces them on the Confirm screen. Cost is negligible (one small call per analysis).
- **Human in the loop:** Always. The parsed table is shown for confirmation/editing before anything downstream uses it. The physics/flux math is never touched by the LLM.

## AI workflow (n8n)

**Goal of the workflow:** After a campaign is analysed, an LLM reviews *that campaign's own* results and produces a plain-language quality report — which spots look anomalous, and which have low R² and shouldn't be trusted — shown in the app with the results, reviewable and downloadable. No cross-campaign comparison; no automatic email.

**Trigger:** App webhook on analysis completion — the app POSTs this campaign's per-spot results (Nr, GPS, light/dark, CO₂ flux, CH₄ flux, R²_CO2, R²_CH4).

**Nodes, in order:**
1. **Trigger — app webhook** receiving the campaign's per-spot results.
2. **AI node** — LLM reviews the results and flags spots with anomalous flux (relative to the others in this set) or R² below 0.80; returns JSON `[{nr, gps, gas, issue, severity}]`.
3. **Format node** — turn the JSON into a readable report (short summary + list of flagged spots).
4. **Return to app** — POST the report back to the app, where it is stored with the analysis and shown on the results screen (and included in the download).

**Connection to the app:** Two-way — app → n8n (results out on completion), n8n → app (quality report back in).

**Error handling:** AI node fails / invalid JSON → retry once, then return "Automatic quality check unavailable — please review R² values manually"; the flux numbers themselves are computed by the app regardless. If n8n is unreachable, the results screen still shows all fluxes with a "quality check pending/unavailable" note. The core tool never depends on n8n being up.

**Runs:** On demand — once per campaign, when an analysis is finished.

## RAG assessment

**Verdict:** Not needed

**Reasoning:** The app has no document corpus to search. Each analysis carries its own self-contained numeric data (a concentration file, notes, temperature, pressure) and is processed by math, not by answering open-ended questions over text. There is nothing to retrieve; a vector store would sit empty. RAG would only make sense if the app later grew a searchable library of papers or documents to ask questions about — a different app.

## MCP assessment

**Verdict:** Not needed

**Reasoning:** Although the app will accumulate saved campaigns with clean verbs (list campaigns, get fluxes, get spot detail), the user does not want to query the data conversationally from an outside assistant. The value is in the visual, screen-bound workflow — inspecting regression plots and supervising the pipeline. An MCP server would be unused convenience, so it is not planned.

## Autonomous agent assessment

**Verdict:** Not needed

**Reasoning:** The whole workflow is a focused desk session — return from the field with files, upload, inspect Plotly regression fits, download results. That is deep, visual, screen-bound work with nothing worth doing by texting from a phone. An autonomous chat agent would be a toy bolted on, not a tool the user would reach for.

## Feature specifications

### Feature 1: Import the four sources
- **Description:** The user uploads their four files, sets chamber constants and time-offset, names the analysis, and starts it.
- **Input:** LI-7810 tab-delimited txt (2 header rows then `DATA` rows; CO₂ ppm, CH₄ **ppb**, Unix `SECONDS`); notes file (Word/Excel/CSV; columns Nr/Start/Stop/GPS/light-dark/location; times like `9.38`); temperature xlsx (Date/Temp ~every 30 s); pressure file (format may vary, LLM-parsed). Chamber constants pre-filled (area 0.0625 m², volume 15.625 L); time-offset in seconds (default 0). Max file size ~50 MB.
- **Output:** Files stored on disk and linked to a new Analysis record; user advanced to the Confirm-notes screen.
- **Where it's used:** Upload / New analysis screen (step 1).
- **Dependencies:** None upstream — the entry point; feeds everything downstream.
- **Edge cases:**
  - Empty input: a required file missing → block Run, highlight which file is absent.
  - Wrong format: LI-7810 file without expected columns → "This doesn't look like a LI-7810 export — expected columns SECONDS, CO2, CH4."
  - External service doesn't respond: n/a at upload (no external call yet).
  - Duplicate data: same file twice, or an analysis name that already exists → warn, offer to rename or overwrite.

### Feature 2: Time-shift correction
- **Description:** The user enters an offset (seconds) that is added to the LI-7810 timestamps before matching, correcting for instrument-clock drift versus real time.
- **Input:** An integer/float number of seconds (may be negative), default 0.
- **Output:** All LI-7810 timestamps shifted by the offset; the applied offset is recorded on the Analysis and shown per spot and in the log.
- **Where it's used:** Upload screen (set before Run); the effect is visible in matching and the per-spot detail.
- **Dependencies:** Feature 1 (the concentration file must be loaded).
- **Edge cases:**
  - Empty input: treated as 0 (no shift).
  - Wrong format: non-numeric offset → validation error before Run.
  - External service doesn't respond: n/a (local computation).
  - Duplicate data: n/a; re-running with a new offset produces a new result set for the same analysis.

### Feature 3: Auto-match by timestamp
- **Description:** Slices the continuous 1 Hz concentration stream into per-spot windows from the (confirmed, offset-corrected) notes, and attaches the nearest-in-time temperature and pressure to each spot.
- **Input:** Confirmed notes (start/stop per spot), offset-corrected concentration readings, temperature series, parsed pressure series.
- **Output:** For each spot, the set of concentration readings inside its window, each annotated with the temperature and pressure used; stored as `Reading` rows.
- **Where it's used:** Runs after the Confirm step; results feed the fitting.
- **Dependencies:** Features 1, 2, and the notes parser (smart feature 1).
- **Edge cases:**
  - Empty input: a spot whose window contains no concentration data → skip the spot, flag in log.
  - Wrong format: stop before start (missed by validation) → skip that spot, flag it.
  - External service doesn't respond: temperature/pressure matching is local; if the pressure parse failed upstream, the spot is flagged "no pressure."
  - Duplicate data: repeated GPS (e.g. redo `3!`, or paired light/dark sharing a GPS) is expected and preserved — GPS is the spatial identity, light/dark distinguishes the measurement type; never merge a light and a dark measurement.

### Feature 4: Fit slope + compute flux
- **Description:** For each spot and each gas, fits a linear regression of concentration vs. time over the window start+30 s → start+5 min 30 s (skip first 30 s, fit next 5 min / 300 points), obtains slope and R², and applies the closed-chamber flux formula to produce flux per m²·s and the full unit ladder.
- **Input:** The per-spot `Reading` set, chamber area and volume, temperature and pressure per spot. CH₄ is in **ppb** and is converted to ppm (÷1000) before flux math.
- **Output:** Two `FluxResult` rows per spot (CO₂, CH₄), each with slope, R², and the full unit ladder (µmol/m²/s, µmol/m²/h, mol/m²/h, g C/m²/day, kg/m²/h, kg/ha/h, kg/ha/day, kg/ha/year, Mg/ha/year, Mg/ha/year CO₂-equivalent).
- **Where it's used:** Runs after matching; results shown on the results table and per-spot detail. Pure code — no LLM.
- **Dependencies:** Feature 3.
- **Edge cases:**
  - Empty input: too few valid points after `nan` removal to fit → skip the gas for that spot, flag it.
  - Wrong format: window unexpectedly shorter than 5 min 30 s (should not happen — protocol is ≥6 min) → fit what's available and flag "short window."
  - External service doesn't respond: n/a (local math).
  - Duplicate data: n/a at this stage; each spot's fit is independent.

### Feature 5: Results + per-spot supervision + export
- **Description:** Shows the campaign's results table (with n8n quality flags), lets the user inspect any spot's regression fit, view the processing log, and save/download the results.
- **Input:** The computed `FluxResult` rows, `Reading` slices for plotting, and the n8n quality report.
- **Output:** On-screen results table; interactive per-spot Plotly plot (points + fitted line, per gas); processing log; download to Excel (.xlsx) or tab-delimited txt with the full column set and unit ladder.
- **Where it's used:** Results screen (step 3), with per-spot detail and processing log opening from it.
- **Dependencies:** Feature 4 and the n8n workflow (for flags; results still show if n8n is unavailable).
- **Edge cases:**
  - Empty input: no computed results (all spots skipped) → message explaining why, linked to the log.
  - Wrong format: n/a (internal data).
  - External service doesn't respond: n8n unavailable → show results with "quality check unavailable."
  - Duplicate data: re-running an analysis → offer to overwrite the previous result set or save as a new named analysis.

### Feature (smart): Field-notes parser
See "Smart features (LLM via API) → Smart feature 1" above for the full specification.

## R script as reference (method-of-record)
The original R script is kept in `reference/`, cleaned up as an early build step (remove the hard-coded `C:/Users/...` paths; point it at the repo's sample files so it runs out of the box). It is **not** called by the running app — it is an independent, parallel expression of the same method, used to validate that the Python tool produces the same fluxes on a known campaign (e.g. 2 July 2026 Kampinos). Changes made in the R script do **not** automatically reach the app; to apply one, ask the coding agent to port the specific change into the Python code, then re-validate. If R and Python ever disagree, that disagreement is itself useful information.

## Open questions / assumptions to confirm
- **Chamber constants** area 0.0625 m² and volume 15.625 L are taken from the 0.25 m cube; confirm these are the real dimensions of every chamber used. *(assumption — confirm before building)*
- **IMGW pressure file format** is unknown; matching is designed as nearest-in-time reading to each spot, and the LLM parser absorbs whatever shape arrives. *(assumption — confirm before building)*
- **Low-R² flag threshold** defaults to 0.80 and is adjustable in settings. *(assumption — confirm before building)*
- **CSV** as a third export format alongside Excel and txt. *(assumption — confirm before building)*
- **Pressure units** — flux math expects a consistent pressure unit (e.g. hPa/kPa); confirm the unit of the uploaded IMGW data so conversion is correct. *(assumption — confirm before building)*
