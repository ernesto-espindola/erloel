# SAP HANA Health Check – HTML Report Generation Prompt

---

## HOW TO USE THIS TEMPLATE

1. Run the HANA Health Check script on the target system
2. Copy the full script output (from `[SCRIPT-Info]` lines through the parameter table)
3. Paste it into the **[PASTE HEALTH CHECK OUTPUT HERE]** section below
4. Send the entire prompt to Claude

---

## PROMPT (copy everything below this line)

---

From the following SAP HANA database health check output, create an interactive HTML report using the exact style and structure described below. Output only the complete HTML code — no explanations, no markdown fences, no comments outside the HTML.

---

### STYLE REQUIREMENTS

> **IMPORTANT — LOCKED DESIGN SYSTEM:** All reports must use the exact same visual style as established below. Do not deviate from colors, fonts, spacing, or component patterns.

#### Color Palette (exact hex values — do not change)
| Role | Value |
|------|-------|
| Primary blue | `#0057a8` |
| Dark blue | `#003366` |
| Accent cyan | `#00b4e6` |
| Page background | `#e8f4fd` |
| Card/section background | `#ffffff` |
| Table row alt | `#f0f7ff` |
| Table hover | `#d0e8ff` |
| Info box background | `#f0f7ff` |
| Danger red | `#d9534f` |
| Warning orange | `#f0ad4e` |
| OK green | `#5cb85c` |
| Pill red bg/text | `#fde8e8` / `#a02020` |
| Pill orange bg/text | `#fff3cd` / `#856404` |
| Pill green bg/text | `#d4edda` / `#155724` |
| Pill blue bg/text | `#cce5ff` / `#004085` |
| Pill grey bg/text | `#e9ecef` / `#495057` |

#### Typography
- **Font family:** `'Segoe UI', Arial, sans-serif`
- **Base size:** 14px
- **Section title:** 1rem, weight 700, color `#003366`
- **Table:** 0.8rem
- **Labels/badges:** 0.7–0.75rem, uppercase, letter-spacing 0.3–0.5px

#### Header (sticky, `top:0`, `z-index:1000`)
- Background: `linear-gradient(135deg, #003366 0%, #0057a8 60%, #00b4e6 100%)`
- Padding: 14px 24px
- Contains: `<div class="header-logo"></div>` (app will inject SAP logo PNG here — leave the div empty), report title in white 1.25rem bold, metadata row (SID, Host, Instance, Tenant, Version, Type) in `#d0eaff` 0.78rem, and an environment badge
- Environment badge: background `#e65c00`, white text, 0.72rem bold, 3px 10px padding, border-radius 12px, uppercase

#### Navigation bar (sticky, `top:60px`, `z-index:999`)
- Background: `#003366`, padding 6px 18px, overflow-x auto
- Pill buttons: color `#a8d0f0`, 0.75rem, border-radius 20px, 5px 13px padding
- Active/hover pill: background `#0057a8`, color `#fff`
- **First pill: "📋 Executive Overview" → scrolls to id="sx"**
- One pill per data section (s0–s10), with emoji icon prefix
- **Last pill: "✅ Action Plan" → scrolls to id="sap"**

#### KPI Summary Cards (grid, `auto-fill minmax(190px,1fr)`, gap 14px)
- White background, border-radius 10px, box-shadow `0 2px 6px rgba(0,83,168,.12)`
- Top border 4px: danger=`#d9534f`, warn=`#f0ad4e`, ok=`#5cb85c`, info=`#0057a8`
- Clickable (scrolls to section), hover: translateY(-3px) + stronger shadow
- Value: 1.6rem bold; label: 0.72rem uppercase grey; sub-text: 0.72rem `#888`
- Value color matches card type: danger=`#d9534f`, warn=`#c87f0a`, ok=`#3d8b3d`, info=`#0057a8`

#### Sections
- White background, border-radius 10px, box-shadow `0 2px 6px rgba(0,83,168,.1)`
- Collapsible header: padding 14px 18px, cursor pointer, hover background `#f0f7ff`
- Header contains: emoji icon (1.2rem) + title (1rem bold `#003366`) on left; badge + chevron (▼/▶ in `#0057a8`) on right
- Body: padding 18px, hidden by default (`display:none`), shown when `.open`

#### Tables
- `thead`: background `#003366`, color `#fff`, padding 9px 12px, font-weight 600
- `tbody` even rows: `#f0f7ff`; hover: `#d0e8ff`
- `td`: padding 7px 12px, border-bottom `1px solid #e8f0f8`
- Wrapped in `.tbl-wrap` with `overflow-x:auto`, border-radius 8px, box-shadow `0 1px 4px rgba(0,0,0,.08)`

#### Status Pills (inline `<span class="pill pill-{color}">`)
- Padding 2px 9px, border-radius 10px, 0.7rem bold
- Colors: red, orange, green, blue, grey — exact values from palette above

#### Progress Bars (inside table cells for size/percentage columns)
- Container `.bar-wrap`: flex, align-items center, gap 8px, min-width 110px
- Track `.bar-bg`: flex:1, background `#e0ecf8`, border-radius 4px, height 10px
- Fill `.bar-fill`: gradient `linear-gradient(90deg, #0057a8, #00b4e6)`; warn variant: `linear-gradient(90deg, #f0ad4e, #e65c00)`; danger: `linear-gradient(90deg, #d9534f, #a00)`
- Label: 0.72rem `#444`, min-width 36px, text-align right

#### Info Boxes (left-bordered)
- Border-left 4px, border-radius `0 8px 8px 0`, padding 12px 16px, 0.85rem
- Blue (default): border `#0057a8`, background `#f0f7ff`
- Green: border `#5cb85c`, background `#f0fff4`
- Orange: border `#f0ad4e`, background `#fffdf0`
- Red: border `#d9534f`, background `#fff5f5`
- `h4` inside: 0.85rem bold, margin-bottom 6px

#### Action Items List
- `<ul class="action-list">` — no list-style, padding 0
- Each `<li>`: padding 5px 0 5px 22px, `::before` content `'▶'` color `#0057a8`, 0.83rem, border-bottom `1px solid #e8f0f8`

#### Sparkline / Horizontal Bar Charts (for categorical data)
- Container `.sparkline-wrap`: flex column, gap 2px
- Each row: label (90px, right-aligned, `#555`, 0.72rem) + bar track (flex:1, `#e0ecf8`, 14px height) + value (60px, `#333`, right-aligned)
- Bar fill: colored div inside track, with inline value text in white 0.68rem bold

#### SVG Trend Line Charts (for time-series data)
- ViewBox `0 0 800 80`, `preserveAspectRatio="none"`, 100% width, 80px height
- Area fill: gradient from `color@0.3` to `color@0.02`; line: stroke 2px, no fill, stroke-linejoin round
- Data point circles (r=3) and value labels at first, last, and midpoint
- Memory trend color: `#0057a8`; CPU trend color: `#00b4e6`

#### Version Banner
- Background: `linear-gradient(135deg, #003366, #0057a8)`, border-radius 10px, padding 20px 24px
- Flex row, wrap, gap 14px; white text
- Installed version: 1.1rem bold; ECS standard: 0.95rem `#a8ffd0`
- Match badge: border-radius 20px, 0.8rem bold — OK: `#5cb85c` bg white text; WARN: `#f0ad4e` bg white text

#### Glossary Tooltips
- Every HANA technical term, table name, parameter name, alert ID, system view, and INI file name wrapped in `<span class="term" data-term="KEY">`
- Style: `border-bottom: 1px dashed #0057a8`, color `#0057a8`, cursor help
- Tooltip div `#tooltip`: `position:fixed`, background `#003366`, white text, padding 10px 14px, border-radius 8px, 0.78rem, max-width 280px, z-index 9999, box-shadow `0 4px 12px rgba(0,0,0,.4)`, pointer-events none
- Tooltip title (`<strong>`): color `#a8d0f0`
- JavaScript: mousemove positions tooltip at cursor+14px offset (clamped to viewport); mouseleave hides it

#### Footer
- `text-align:center`, 0.75rem, color `#666`, padding 16px
- Content: `Health Check Report | SID: {SID} | Generated: {date} | Script: {version}`

#### Responsive
- All grids use `grid-template-columns: repeat(auto-fill, minmax(Xpx, 1fr))`
- KPI cards: minmax(190px); env grid: minmax(200px); on ≤700px: KPI cards 2 columns, header metadata hidden

#### Technical
- Single `.html` file, no external dependencies, no CDN links
- All CSS in `<style>` in `<head>`; all JS in `<script>` before `</body>`
- No HTML comments; no text outside HTML tags
- SVG logo inline only (no `<img>` tags)

---

### SECTIONS TO GENERATE (always include all sections, even if data shows 0 / none found)

| # | Section | Icon | Content |
|---|---------|------|---------|
| X | Executive Overview | 📋 | **Non-technical section for management audiences — no HANA jargon.** Always the FIRST section (id="sx"). Nav pill: "📋 Executive Overview". Contents: (1) Health-at-a-Glance grid (`.health-grid`) — one `.health-item` per key dimension (Disk Space, Security, Memory, Backups, Alerts, Performance) each with a traffic-light emoji (🔴 critical / 🟡 warning / 🟢 ok), a short label, and a one-line plain-English status. (2) Critical impact cards (`.exec-grid`) — one `.exec-card.critical` per issue that could cause downtime within days; each card has a `<h4>` title, a `.biz-impact` line starting "Business Risk:", and a `.biz-action` line starting "Action:". (3) Warning cards (`.exec-card.warning`) — issues requiring attention within weeks. (4) A plain-language summary paragraph. Derive all content from the actual data found — do not invent or estimate. |
| 0 | Environment Summary | 🖥 | KPI cards + environment grid (SID, host, instance, cloud, CPU, RAM, volume, MDC, replication, memory usage) |
| 1 | HANA Database Version | 🔢 | Version banner: installed vs latest, SPS/revision match badge, upgrade recommendation if behind |
| 2 | ECS Standard Parameters | ⚙ | Count of ERROR / OK / OK-strictness params; table of ERROR rows only (6 columns); **after each ERROR row add a `<tr><td colspan="6"><div class="consequence">` block explaining in plain English the security or stability consequence of that deviation and the fix command**; interpretation box; notable non-error deviations list |
| 3 | P1 Alerts – Last 40 Days | 🚨 | Count per DB (SYSTEMDB / tenant); consolidated alert table grouping by Alert ID; recommended actions list |
| 4 | Big Technical Tables | 🗄 | Count, total memory GB, total disk GB; full table with schema, table name, type, records, disk GB (with bar), mem GB, LOB indicator, notes; **if any table consumes > 100 GB disk or > 20 GB memory, add a red `.esc-banner` at the top of the section body**; recommended actions per table |
| 5 | Tables > 1.5 Billion Records | 📊 | Count; if 0 show green info box; if found show table with schema/table/records/partition; growth watch note |
| 6 | Out-of-Memory Events | 💾 | Count; memory utilisation grid (allocated, used, top allocators); preventive recommendations |
| 7 | CPU Spikes ≥ 95% | ⚡ | Count; table with timestamp, CPU%, bar chart, average CPU context; root cause correlation; recommended actions |
| 8 | Failed Backups | 💿 | Count; danger info box with pattern analysis (single-day vs spread, duration pattern, affected DBs); full detail table; recommended actions |
| 9 | Additional Risks | ⚠ | Table with: risk area, observation, severity pill, recommended action — derive from all anomalies found in the data |
|10 | Minichecks

	Analyze and check for what's abnormal, concerning or critical, create graphs for easy interpretation of results and sugest action item for:


		HANA_Resources_CPUAndMemory_2.00.060

          

		HANA_SQL_ExpensiveStatements_2.00.040+

		HANA_Tables_LargestTables_2.00.060+

		HANA_Configuration_Overview_2.00.080+

		HANA_Disks_Data_Partitions_2.00.040+

		HANA_IO_DiskDetails_2.00.020+

               
		HANA_IO_Savepoints_2.00.060+ |
| AP | Consolidated Action Plan | ✅ | **Always the LAST section (id="sap"). Nav pill: "✅ Action Plan".** Consolidate ALL recommended actions from every section above into a single prioritised plan. Group into 3 tiers: **Priority 1 — Immediate (≤48h)** (`.ap-card.p1`), **Priority 2 — This Week** (`.ap-card.p2`), **Priority 3 — This Month** (`.ap-card.p3`). Each action item is an `.ap-card` with: `<h4>` numbered title, `<p>` one-sentence description, and `.ap-tags` row with badges: `.ap-tag.urgent` for urgency, `.ap-tag.owner` for owner (DBA / Basis / Security / AppTeam), `.ap-tag.effort` for effort estimate, `.ap-tag.prevents` for what failure it prevents. Do not repeat analysis — only list the action, owner, effort, and consequence. |



### LOGIC RULES

- **Database name:** Extract SID from `[environment] - SID:` line. Tenant name from backup/alert data or `PS4-` prefixed metrics
- **Version:** Extract from `HDB version:` line. Compare to latest released listed on HANA_latest_release.txt file
- **Parameters:** Parse the ASCII table at the end of the output. Count rows with `ERROR` status. List only ERROR rows in the report table. Mention notable `OK (strictness high/low)` deviations in a sub-list
- **P1 Alerts:** Parse `PS4-ALERT DETAILS` and `P1 Alerts on SYSTEMDB`. Group alert rows by Alert ID. Sum NUM_OF_EVENTS per Alert ID for the event count column
- **Big Technical Tables:** Parse `List of Technical Tables detected`. Use DISK_GB column for bar chart scaling (max = largest value = 100%). Flag tables with LOB columns. Add contextual archiving note per known SAP table name
- **Large records:** Parse `Tables bigger than 1.5 billion records`. If 0, green box. If found, build table
- **OOM:** Parse `OOM events on the last 40 days` for both SYSTEMDB and tenant. If 0, green box. Always show memory utilisation grid from `MEMORY USED BY INDEXSERVER` and `Top 10 Memory Allocators`
- **CPU:** Parse `CPU spikes on the system` count and `CPU events higher than 95 percent` detail. Show average CPU from `CPU Average` line
- **Backups:** Parse `Failed Backup Execution details`. Count total rows. Analyse time pattern (all same day? spread?). Duration pattern (< 15s = immediate rejection). Affected DBs
- **Additional risks:** Auto-derive from: low plan cache hit ratio events, replication role, license alert count, TLS parameter deviations, persistent delta merge backlog, any other anomaly
- **Executive Overview:** Always generate this section. Use only plain English — no system view names, no parameter names, no HANA internals. Classify each dimension as 🔴/🟡/🟢 based on severity of actual findings. Critical cards = issues that could cause unplanned downtime within days if unresolved. Warning cards = issues requiring action within weeks.
- **Disk space KPI card:** Only add a `.kpi-critical` KPI card labelled "DISK SPACE" if the health check output contains OS-level filesystem data (e.g. `df -h` output) confirming free space < 20 GB or < 15% on the HANA data volume. The HANA_Disks_Data_Partitions minicheck reports HANA-internal ALLOC_GB (pre-allocated file size) and USED_GB (written data) — these are NOT filesystem capacity metrics. Do NOT derive a disk warning from ALLOC_GB/USED_GB ratios. If USED_GB is close to ALLOC_GB (> 90%), add only a blue informational box: "HANA data volume pre-allocation is near its current boundary. HANA will auto-extend onto available filesystem space. Monitor /hana/data filesystem free space to ensure room for growth." If no OS filesystem data is present in the output, do not add any disk warning at all.
- **Action Plan:** Consolidate every "recommended action" item from all sections. Do not duplicate — if the same action appears in multiple sections, list it once in the highest-priority tier. Assign owner based on action type: parameter changes and memory tuning → DBA; patch/upgrade → Basis; TLS/CVE → Security; application table archival → AppTeam.

---

### GLOSSARY MINIMUM TERMS (always define these if they appear in the data)

SPS, Revision, PatchLevel, INIfile, ECS, global.ini, indexserver.ini, nameserver.ini,
sslminprotocolversion, Alert29, Alert39, Alert140, Mergedog, PlanViz, AdmissionControl,
TechnicalTable, NearlineStorage, AuditLogArchive, M_CS_TABLES, M_RS_TABLES, OOM,
M_DEV_MEMORY_COMPONENT_ALLOCATORS, M_LOAD_HISTORY_SERVICE, WorkloadClass,
StatementTimeout, Backint, PlanCacheHitRatio, PlanStability, DisasterRecoveryPrimary,
TLSProtocol, DeltaMerge, SOFFCONT1, REPOLOAD, RSAU_LOG, REPOSRC, EDID4,
OBJECT_HISTORY, DBTABLOG, SWWCNTP0, CDPOS, BALDAT, D010TAB, M_BACKUP_CATALOG,
M_SQL_PLAN_CACHE, M_SERVICE_REPLICATION, M_OUT_OF_MEMORY_EVENTS, M_BLOCKED_TRANSACTIONS

Add any additional terms found in the specific output (table names, parameter names, alert details).

---

### OUTPUT FORMAT

- Single `.html` file, no external resources
- All CSS in a `<style>` block in `<head>`
- All JavaScript in a `<script>` block before `</body>`
- No HTML comments
- No text outside the HTML tags

---

## [PASTE HEALTH CHECK OUTPUT HERE]

```
<<< REPLACE THIS LINE WITH THE FULL HANA HEALTH CHECK SCRIPT OUTPUT >>>
```

---
