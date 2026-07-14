# Flux Calculation — Frontend Assignment

> Brief for the frontend engineer. Build the full UI on **mock data only** — every
> point that would talk to a server is marked **`TODO: connect to API`** with the mock
> shape to use meanwhile. Nothing here describes backend internals; treat the backend
> as a black box behind the typed API client (`src/api/`).

---

## Overview

Flux Calculation is a **local, single-user, desktop-style web tool** for greenhouse-gas
researchers who run closed-chamber measurements with an LI-7810 instrument (the author
and a few lab friends). Returning from the field with four raw files — a 1 Hz CO₂/CH₄
concentration log, hand-typed start/stop time notes, a temperature spreadsheet, and a
pressure file — the user uploads them, reviews the machine-cleaned notes, and gets a
per-spot table of computed CO₂ and CH₄ fluxes with regression plots they can inspect.
The whole experience is a focused desk session: upload → confirm → results, with detail
and audit views hanging off the results. The tone is **a competent, friendly field
colleague**: plain sentences, no jargon in the UI, every transformation visible for
supervision. Data-first and uncluttered, like a modern lab tool — not corporate SaaS.

---

## Screens and pages

The app is a **stepper-driven single flow** (Upload → Confirm → Results) plus two
detail views that open from Results, and a Home/landing list of saved analyses.

### 0. Home / Saved analyses (landing)
- **Purpose:** entry point; pick up a past analysis or start a new one.
- **Layout:**
  - **App header** (persistent): logo + "Flux Calculation" wordmark on the left; slogan
    *"From messy field notes to clean fluxes"* as a muted subtitle; a **+ New analysis**
    primary button on the right.
  - **Body:** a list/grid of **analysis cards**, newest first. Each card shows analysis
    name, work date, spot count, created-at, and a small status chip (`Complete`,
    `Draft`, `Needs review`). Clicking a card opens it at the furthest step it reached.
  - **Empty state** (first run): centered illustration + friendly prompt and a big
    upload CTA (see [States](#states)).
- **Primary actions:** New analysis; open an existing analysis; (secondary) delete an
  analysis via a card overflow menu with confirm.

### 1. Upload / New analysis  *(stepper step 1)*
- **Purpose:** collect the four files + constants, name the analysis, and Run.
- **Layout:**
  - **Stepper bar** at top: `Upload → Confirm → Results`, step 1 active.
  - **Analysis meta** card: text input **Analysis name**; **Work date** picker.
  - **Four file-drop zones** (stacked on mobile, 2×2 grid on wide), each a labeled
    dropzone with icon, accepted formats, and state (empty / file attached with name +
    size + remove / rejected with reason):
    1. **LI-7810 concentration** — `.txt`
    2. **Time-window notes** — `.docx`, `.xlsx`, `.csv`
    3. **Temperature** — `.xlsx`
    4. **IMGW pressure** — any (format varies)
  - **Chamber constants** card: **Area (m²)** pre-filled `0.0625`; **Volume (L)**
    pre-filled `15.625`; **Time-offset (seconds)** pre-filled `0` (accepts negative),
    with helper text "Add/subtract seconds if the LI-7810 clock drifted from real time."
  - **Footer action bar:** **Run analysis** (amber CTA, disabled until all four files
    present and constants valid) + a subtle "Save as draft" link.
- **Primary actions:** attach/remove each file; edit constants & offset; **Run analysis**.
- **Validation:** missing required file blocks Run and highlights the empty dropzone;
  non-numeric constants/offset show inline errors; wrong-looking LI-7810 file surfaces
  the backend's format message inline (e.g. *"This doesn't look like a LI-7810 export —
  expected columns SECONDS, CO2, CH4."*). Duplicate analysis name → warn, offer rename
  or overwrite.

### 2. Confirm parsed notes  *(stepper step 2)*
- **Purpose:** review and edit the machine-cleaned time-notes **before** matching runs.
  Human-in-the-loop checkpoint.
- **Layout:**
  - **Stepper bar**, step 2 active.
  - **Info banner** explaining what to check ("We cleaned up your field notes. Please
    confirm the times and GPS before we match the data."). If automatic parsing failed,
    this becomes a **warning banner**: *"Automatic parsing failed — please check the
    times below manually."*
  - **Editable table**, one row per spot, columns: **Nr, Start, Stop, GPS, Light/Dark,
    Location**. Every cell is inline-editable. Rows with problems are flagged with a
    warning icon + row highlight (blank/`?` GPS, stop ≤ start, unparseable time). A
    Light/Dark cell is a small select (`light` / `dark`). Add-row / delete-row controls.
  - **Validation summary** strip above or below the table: "2 rows need attention."
  - **Footer action bar:** **Back** (to Upload) and **Approve & match** (primary;
    disabled while any hard error — e.g. stop ≤ start — remains).
- **Primary actions:** edit cells; add/remove rows; **Approve & match**; **Back**.

### 3. Results table  *(stepper step 3)*
- **Purpose:** the payoff — every spot's fluxes, quality flags, and export.
- **Layout:**
  - **Stepper bar**, step 3 active (all steps now clickable to go back).
  - **Results header:** analysis name + work date; **quality-check summary** area (from
    n8n) — a short plain-language summary + count of flagged spots; a **"quality check
    unavailable"** note appears here instead when applicable.
  - **Toolbar:** search/filter (by Nr, GPS, light/dark, flagged-only toggle); **sort**
    controls; **Export** split-button (**Excel .xlsx** / **tab-delimited .txt**;
    **CSV** as a third option — *confirm before building*); link to **Processing log**.
  - **Table** — columns: `Nr, date, start, stop, GPS, light/dark, location, CO₂ flux,
    CH₄ flux, R²_CO2, R²_CH4, temperature used, pressure used, time-offset applied`.
    - R² cells are color-coded (low-R² < 0.80 highlighted). Rows the quality check
      flagged as anomalous get a warning chip. Skipped spots show a muted "skipped" row
      with a reason tooltip.
    - Row click → **Per-spot detail**.
  - The **full unit ladder** is not shown in the table (too wide) — it lives in per-spot
    detail and the export.
- **Primary actions:** sort/filter; open a spot; open processing log; export/download;
  re-run (overwrite or save as new).

### 4. Per-spot detail  *(opens from Results; modal on mobile, side panel / route on wide)*
- **Purpose:** supervise a single spot's fit.
- **Layout:**
  - **Header:** "Spot 7 · GPS … · light" + close/back.
  - **Two regression plots** (or a gas toggle) — **CO₂** and **CH₄** — each an
    interactive **Plotly** scatter of concentration points with the **fitted regression
    line** drawn through them; zoom/pan enabled. The fit window (start+30 s →
    start+5 min 30 s) is visually shaded; points outside the fit window shown muted.
  - **Fit facts panel:** slope, R², n points used, points dropped (nan) with count,
    temperature used, pressure used, time-offset applied, fit-window start/stop.
  - **Flags:** any per-spot warnings (low R², short window, no pressure, dropped nans).
- **Primary actions:** toggle gas; zoom/pan/reset the plot; navigate prev/next spot; close.

### 5. Processing log  *(opens from Results; full page or wide drawer)*
- **Purpose:** campaign-wide audit trail of every transformation.
- **Layout:**
  - **Header:** "Processing log — {analysis name}".
  - **Chronological list** of entries, each with a severity icon (info / warning /
    error), a timestamp, and a plain sentence: rows dropped, offset applied, which
    pressure matched to which spot, spots skipped and why, nan drops per spot, etc.
  - **Filter** by severity; **copy/download log** action.
- **Primary actions:** filter; download; back to Results.

---

## Navigation and user flows

**Global model.** A persistent **app header** (logo, wordmark, New-analysis button).
Inside an analysis, a **stepper bar** (`Upload → Confirm → Results`) is the primary
navigation: the current step is highlighted; completed steps are clickable to go back;
future steps are disabled until reached. **Per-spot detail** and **Processing log** open
*from* the Results screen (row click / toolbar link) and return to it on close — they are
not stepper steps. Home is reachable via the logo.

**Flow A — Run a new analysis (happy path)**
1. Home → click **+ New analysis** → Upload screen.
2. Drop the four files; confirm/adjust area, volume, offset; type a name & date.
3. Click **Run analysis** → a **live step indicator** shows progress
   ("Parsing notes… matching temperature… fitting CO₂ and CH₄… done") → lands on Confirm.
4. On **Confirm**, review the cleaned notes table, fix any flagged rows, click
   **Approve & match**.
5. Matching + fitting run (step indicator again) → lands on **Results**.
6. Scan the table, click a spot to inspect its regression fit, then **Export** to Excel.

**Flow B — Reopen and export a past analysis**
1. Home → click an analysis card → opens at Results.
2. Filter to flagged-only, open a low-R² spot, inspect the fit.
3. Export to `.txt` (or download the processing log).

**Flow C — Fix messy notes after a failed parse**
1. During Run, automatic parsing fails → Confirm opens with a **warning banner** and a
   best-effort (or empty) table.
2. User types the start/stop/GPS/light-dark rows by hand; validation clears the errors.
3. **Approve & match** → Results.

**Flow D — Re-run with a corrected time-offset**
1. From Results (or Home), user reopens the analysis and edits the offset on Upload.
2. **Run analysis** → app warns the previous result set will be replaced → user chooses
   **Overwrite** or **Save as new** → new Results.

---

## Visual design

The brief specifies the brand palette; **everything below the palette (scale, spacing,
radius, elevation, dark mode) I am proposing as a modern, clean, accessible system** on
top of it. Built with **Tailwind CSS** — map these into `tailwind.config` tokens.

### Colour palette (from the brief)
| Role | Hex | Use |
|---|---|---|
| **Primary** — deep teal | `#0F766E` | headers, active stepper, primary buttons, links, focus ring |
| Primary hover/darker | `#115E59` | button hover, pressed |
| Primary tint (bg) | `#CCFBF1` / `#F0FDFA` | selected rows, chips, subtle fills |
| **Secondary** — warm brown | `#92400E` | secondary accents, category markers, "dark" measurement tag |
| **Accent / CTA** — amber | `#F59E0B` | the **Run analysis** button and only truly primary CTAs |
| Accent hover | `#D97706` | CTA hover |
| **Background** — near-white | `#F8FAFC` | app background |
| Surface / card | `#FFFFFF` | cards, tables, modals |
| **Text** — slate | `#1E293B` | primary text |
| Text muted | `#64748B` | secondary text, helper, placeholders |
| Border / divider | `#E2E8F0` | table lines, card borders, input borders |

**Semantic (proposed — accessible, clean):**
| Role | Hex | Use |
|---|---|---|
| Success | `#15803D` | green — good R², completed |
| Warning | `#B45309` | amber-brown — flags, low-R², "needs review" |
| Error | `#B91C1C` | red — hard validation errors, skipped spots |
| Info | `#0F766E` | teal — informational banners |

**Data-viz (Plotly, proposed):** CO₂ series `#0F766E` (teal), CH₄ series `#92400E`
(brown) — reuse brand colours so the two gases read consistently everywhere; regression
line a darker shade of each; muted grey `#94A3B8` for out-of-window points.

### Typography (proposed)
- **Font:** system UI / Inter stack — `Inter, ui-sans-serif, system-ui, -apple-system,
  "Segoe UI", Roboto, sans-serif`. **Tabular numbers** (`font-variant-numeric:
  tabular-nums`) for all flux/R²/time columns so figures align.
- **Scale (rem / px @16):** Display 2.25/36 (700) · H1 1.875/30 (700) · H2 1.5/24 (600)
  · H3 1.25/20 (600) · Body-lg 1.125/18 · **Body 1/16 (400)** · Small 0.875/14 · Caption
  0.75/12. Line-height 1.5 body, 1.25 headings.

### Spacing, radius, elevation (proposed)
- **Spacing scale (px):** 4, 8, 12, 16, 24, 32, 48, 64 (Tailwind 1/2/3/4/6/8/12/16).
  Card padding 24; form field gap 16; section gap 32.
- **Corner radius:** inputs/buttons **8px** (`rounded-lg`); cards/modals **12px**
  (`rounded-xl`); chips/pills **full**. Consistent, gently rounded — scientific, not toy.
- **Elevation:** flat by default (borders over shadows for a data-first feel).
  - Card: `1px` border `#E2E8F0`, no shadow.
  - Raised (dropdown, popover): `shadow-md`.
  - Modal / per-spot detail: `shadow-lg` + backdrop `rgba(15,23,42,0.4)`.
- **Focus ring:** 2px solid primary teal + 2px offset, on every interactive element.

### Light / dark handling (proposed)
Ship **light mode first** (matches the near-white lab-table aesthetic). Provide a
**dark theme** via CSS variables / Tailwind `dark:` so tokens swap cleanly:
- Dark bg `#0F172A`, surface `#1E293B`, border `#334155`, text `#E2E8F0`, muted
  `#94A3B8`. Primary teal lightens to `#2DD4BF` for contrast; amber CTA `#FBBF24`.
- Respect `prefers-color-scheme`; expose a manual toggle in the header. Verify all
  semantic colours still clear WCAG AA in both modes (see [Accessibility](#accessibility)).

---

## Components

Reusable inventory. Every interactive component must define **default, hover, focus,
disabled, loading** states (and error where it takes input).

- **Button** — variants: `primary` (teal), `cta` (amber, Run analysis only),
  `secondary` (outline), `ghost` (text), `danger` (red, destructive). States: default /
  hover / focus / active / disabled / **loading** (spinner + disabled, label → "Running…").
- **Icon button** — overflow menus, close, plot controls. Same state set; 40px min hit area.
- **Text input / number input** — label, optional helper, error text. States: default /
  focus / filled / disabled / error. Number inputs for constants & offset (offset allows
  negative).
- **Date picker** — work date.
- **Select / dropdown** — light/dark cell, sort, export format.
- **File dropzone** — states: idle / drag-over / attached (filename + size + remove) /
  rejected (reason). Shows accepted extensions.
- **Stepper bar** — steps with states: completed (clickable), active, upcoming
  (disabled). Shows step number + label.
- **Card** — for analysis list items and grouped form sections; hover state on clickable cards.
- **Data table** — sortable headers, zebra/hover rows, sticky header, right-aligned
  numeric (tabular) columns, per-cell color coding (R²), row flags, clickable rows,
  skipped/muted rows. Editable-cell variant for Confirm screen.
- **Editable cell** — inline text/select edit with per-cell validation state.
- **Chip / badge** — status (`Complete`/`Draft`/`Needs review`), quality flag
  (`anomalous`/`low R²`), light/dark tag. Colour by semantic role.
- **Banner / alert** — info / warning / error, full-width, dismissible where appropriate
  (parse-failed, quality-check-unavailable, duplicate-name warnings).
- **Toast** — transient confirmations ("Exported flux-results.xlsx", "Analysis saved").
  Success / error variants; auto-dismiss + manual close.
- **Modal / drawer** — per-spot detail (drawer on wide, modal on mobile), confirm
  dialogs (overwrite, delete). Focus-trapped.
- **Live step / progress indicator** — the pipeline runner: ordered steps ("Parsing
  notes… matching temperature… fitting CO₂ and CH₄… done") with per-step spinner →
  check. Never a frozen blank screen.
- **Regression plot** — Plotly wrapper: scatter + fitted line, shaded fit window, gas
  toggle, zoom/pan/reset. Loading + empty + error states.
- **Empty state** — illustration/icon + heading + explanation + primary action.
- **Skeleton loaders** — for table rows, cards, and the plot area.
- **Tooltip** — flag explanations, skipped-row reasons, truncated cells.
- **Pagination / virtualized rows** — if a campaign has many spots (assume up to a few
  hundred readings-worth; table rows are per-spot, typically < 100 — virtualize if needed).

---

## States

For every data-driven screen, define **empty**, **loading (skeleton)**, and **error**:

| Screen | Empty | Loading | Error |
|---|---|---|---|
| **Home / list** | *"No analyses yet. Upload your LI-7810, time notes, temperature and pressure files to calculate your first fluxes."* + upload CTA. | Skeleton cards. | *"Couldn't load your analyses."* + Retry. |
| **Upload** | (form always present) — Run disabled until valid; per-field errors inline. | On Run: **live step indicator** overlay/section. | Format/validation errors inline per file/field; Run failure → error banner, form preserved. |
| **Confirm** | Table with a message if 0 rows parsed ("No rows found — add them manually below."). | Skeleton table rows while parsing. | **Warning banner** on parse failure; per-row/per-cell validation errors. |
| **Results** | *"No results yet"* / if all spots skipped: message explaining why, linked to the **Processing log**. | Skeleton table + skeleton summary; step indicator during compute. | Error banner + Retry; quality-check absence shows **"quality check unavailable"** (not an error). |
| **Per-spot detail** | "No readings in this spot's window" (skipped spot) with reason. | Skeleton plot + skeleton fit-facts. | "Couldn't load this spot" + close/retry. |
| **Processing log** | "No log entries." | Skeleton list. | Error + Retry. |

Notes: skeletons match final layout (no layout shift). The pipeline **never dead-ends** —
parse failure falls back to manual editing; n8n absence still shows fluxes.

---

## Responsiveness

**Mobile-first**, though the primary target is a desktop desk session — build so it works
on a phone and *scales up*, not the reverse.

- **Breakpoints (Tailwind):** base < 640 (mobile), `sm` 640, `md` 768, `lg` 1024,
  `xl` 1280.
- **App header:** wordmark + New-analysis button always; slogan hidden below `sm`.
- **Stepper:** compact numbered dots with active label on mobile; full labelled steps ≥ `md`.
- **Upload dropzones:** single column stacked on mobile → **2×2 grid** ≥ `md`; constants
  card full-width mobile → beside meta ≥ `lg`.
- **Confirm / Results tables:** horizontally scrollable container on mobile with the Nr
  column sticky; full table ≥ `lg`. Consider a stacked "card per spot" fallback for the
  results table below `sm` (each spot as a labeled card).
- **Per-spot detail:** full-screen **modal** on mobile; right-side **drawer** (or split
  route) ≥ `lg` so the plot has room. Plot resizes responsively (Plotly `responsive:true`).
- **Toolbars:** filter/sort/export collapse into an overflow menu on mobile.
- Tap targets ≥ 44px; no hover-only affordances (provide tap/focus equivalents).

---

## Accessibility

Concrete, testable targets — **WCAG 2.1 AA**:

- **Contrast:** all text ≥ **4.5:1** (≥ **3:1** for ≥ 24px/bold and for UI/graphical
  boundaries). Verify amber CTA text (use slate `#1E293B` text on `#F59E0B`, not white),
  teal buttons (white text on `#0F766E` passes), and all semantic colours in **both**
  light and dark. Never signal a flag by colour alone — pair with icon + text.
- **Focus:** visible 2px focus ring on every interactive element; never remove outlines;
  logical tab order; focus moves into modals/drawers and is **trapped**, returns to the
  trigger on close.
- **Keyboard:** full operability without a mouse — stepper, dropzones (Enter/Space +
  file dialog), editable table cells (Tab between cells, Enter to commit, Esc to cancel),
  sort headers, export menu, plot controls, modal Esc-to-close.
- **Labels & semantics:** every input has a `<label>`; icon-only buttons have
  `aria-label`; tables use `<th scope>`; banners use `role="alert"`/`status`; the live
  step indicator is an `aria-live="polite"` region so progress is announced.
- **Alt text:** logo has alt; the empty-state illustration is decorative (`alt=""`); the
  Plotly regression plot has a text summary alternative (slope, R², n) adjacent so the
  fit is not conveyed by the chart alone.
- **Motion:** respect `prefers-reduced-motion` (no spinners-as-only-signal; reduce
  animated transitions).
- **Target size** ≥ 44×44px.

---

## Backend touchpoints

The frontend runs on **mock data only** this phase. Put all network calls behind a typed
client in `src/api/` and back it with in-memory mock fixtures (`src/api/mocks/`) so the UI
is fully clickable. Each touchpoint below is **`TODO: connect to API`** with the mock
shape to build against. Field names mirror the domain model in the brief; treat these as
the contract to confirm with backend later.

### List / open / delete analyses  *(Home)*
- **`TODO: connect to API`** — `GET /analyses`, `GET /analyses/{id}`, `DELETE /analyses/{id}`.
- **Mock shape:**
```json
[
  { "id": "an_001", "name": "Kampinos 2 July", "work_date": "2026-07-02",
    "spot_count": 18, "status": "complete", "created_at": "2026-07-03T09:12:00Z" }
]
```

### Create analysis + upload files + Run  *(Upload)*
- **`TODO: connect to API`** — `POST /analyses` (multipart: 4 files + fields
  `name, work_date, chamber_area_m2, chamber_volume_l, time_offset_seconds`). Returns the
  created analysis + kicks off parsing.
- **Mock:** accept the form, fake a 1–2 s delay stepping through the live indicator, then
  resolve with an analysis id and a parsed-notes payload (below). Simulate the error
  branches too (missing file, bad LI-7810 format, duplicate name) behind a mock flag so
  those UI states are reachable.
```json
{ "id": "an_002", "name": "Wetland A", "work_date": "2026-07-10",
  "chamber_area_m2": 0.0625, "chamber_volume_l": 15.625, "time_offset_seconds": 0,
  "status": "needs_review" }
```

### Parsed notes for confirmation  *(Confirm)*
- **`TODO: connect to API`** — `GET /analyses/{id}/notes` (returns machine-cleaned rows +
  per-row flags); `PUT /analyses/{id}/notes` (save edited rows); `POST
  /analyses/{id}/match` (approve → run matching + fitting).
- **Mock shape** (include a `parse_failed: boolean` at the top level to exercise the
  fallback banner, and per-row `flags`):
```json
{
  "parse_failed": false,
  "rows": [
    { "nr": 1, "start_time": "09:38:00", "stop_time": "09:44:00",
      "gps": "52.301, 20.789", "light_dark": "light", "location": "dam edge",
      "flags": [] },
    { "nr": 2, "start_time": "09:46:00", "stop_time": "09:45:00",
      "gps": "", "light_dark": "dark", "location": "",
      "flags": ["stop_before_start", "gps_missing"] }
  ]
}
```

### Results table  *(Results)*
- **`TODO: connect to API`** — `GET /analyses/{id}/results`. Returns per-spot flux rows +
  the n8n quality summary (which may be absent/unavailable).
- **Mock shape:**
```json
{
  "quality_check": {
    "available": true,
    "summary": "2 of 18 spots look anomalous; 1 has low R² and should not be trusted.",
    "flags": [ { "nr": 7, "gps": "52.30,20.78", "gas": "CH4",
                 "issue": "flux ~4× the campaign median", "severity": "high" } ]
  },
  "spots": [
    { "nr": 1, "date": "2026-07-02", "start": "09:38", "stop": "09:44",
      "gps": "52.301, 20.789", "light_dark": "light", "location": "dam edge",
      "co2_flux_umol_m2_s": 1.83, "ch4_flux_umol_m2_s": 0.0042,
      "r2_co2": 0.997, "r2_ch4": 0.812,
      "temperature_used_c": 21.4, "pressure_used_hpa": 1004.2,
      "time_offset_applied_s": 0, "n_points_co2": 300, "n_points_ch4": 288,
      "flags": [], "skipped": false, "skip_reason": null }
  ]
}
```
- Provide at least one **skipped** spot (`"skipped": true, "skip_reason": "no
  concentration data in window"`) and one **low-R²** spot in the mock.

### Per-spot detail (points + fit)  *(Per-spot detail)*
- **`TODO: connect to API`** — `GET /analyses/{id}/spots/{nr}`. Returns the concentration
  points per gas, the fitted line params, the fit window, and the facts panel data.
- **Mock shape:**
```json
{
  "nr": 7, "gps": "52.30, 20.78", "light_dark": "light",
  "fit_window": { "start": "10:05:30", "stop": "10:10:30" },
  "gases": {
    "CO2": {
      "unit": "ppm",
      "points": [ { "t_s": 0, "value": 412.1, "in_window": false },
                  { "t_s": 31, "value": 415.7, "in_window": true } ],
      "fit": { "slope": 0.118, "intercept": 411.9, "r2": 0.997,
               "n_points": 300, "n_dropped_nan": 2 },
      "flux_ladder": {
        "umol_m2_s": 1.83, "umol_m2_h": 6588, "mol_m2_h": 0.0066,
        "gC_m2_day": 1.71, "kg_m2_h": 0.00029, "kg_ha_h": 2.9,
        "kg_ha_day": 69.6, "kg_ha_year": 25404, "Mg_ha_year": 25.4,
        "Mg_ha_year_co2equiv": 25.4 }
    },
    "CH4": { "unit": "ppb", "points": [], "fit": {}, "flux_ladder": {} }
  }
}
```

### Processing log  *(Processing log)*
- **`TODO: connect to API`** — `GET /analyses/{id}/log`.
- **Mock shape:**
```json
[
  { "ts": "2026-07-10T10:00:01Z", "severity": "info",
    "message": "Applied time-offset +0 s to 21,600 LI-7810 rows." },
  { "ts": "2026-07-10T10:00:03Z", "severity": "warning",
    "message": "Spot 7: 12 of 300 readings dropped (nan)." },
  { "ts": "2026-07-10T10:00:03Z", "severity": "error",
    "message": "Spot 14 skipped: stop 13:33 is before start 13:27 (time notes row 13)." }
]
```

### Export / download  *(Results)*
- **`TODO: connect to API`** — `GET /analyses/{id}/export?format=xlsx|txt|csv` (streams a
  file with the full column set + unit ladder). *(CSV — confirm before building.)*
- **Mock:** generate the file client-side from the mock results (or trigger a stub
  download) so the export button + toast are exercisable.

**Assumptions flagged for confirmation** (from the brief, surface in UI copy/config, not
hard-coded silently): chamber constants `0.0625 m² / 15.625 L`; low-R² threshold `0.80`
(make it a configurable constant in `src/lib/`); pressure unit (label as hPa in the mock,
confirm); CSV as a third export format.
