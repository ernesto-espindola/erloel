# SAP HANA Health Check – Full Report Pipeline Prompt

---

## HOW TO USE

1. Run the HANA Health Check script on the target system
2. Save the full output as `<SID><CUSTOMER>_HANA_Health_Check_report.txt` in the working directory
3. Paste this entire prompt into Claude (replace the placeholder in the last section)
4. Claude will produce both the HTML and Excel files and move them to the customer folder

---

## PROMPT (copy everything below this line and send to Claude)

---

I have a new SAP HANA Health Check output file in my working directory:
`C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory\`

The health check file is named: **[PASTE FILENAME HERE — e.g. HP4REY_HANA_Health_Check_report.txt]**
The customer name for the destination folder is: **[PASTE CUSTOMER NAME HERE — e.g. Dummy_customer]**

Please do the following in sequence:

---

### STEP 1 — Read the health check file

Read the full content of the health check file from the working directory.

---

### STEP 2 — Extract all data variables

From the health check output, extract ALL of the following variables:

| Variable | Where to find it |
|---|---|
| DB_NAME | `SID:` line in `[environment]` section |
| DB_VERSION | `HDB version:` line |
| TENANT_NAME | Prefix used in metric lines (e.g. PS4-COLUMSTORE) |
| HOST | `Installationname:` line |
| INSTANCE | `Instancenumber:` line |
| CLOUD | `Cloud:` line |
| HOST_TYPE | `Hosttype:` line |
| CPU_PHYS | `CPU_PHYS:` line |
| CPU_LOG | `CPU_LOG:` line |
| PHYS_MEM | `PHYS_MEM:` line |
| VOLUME | `Volume Size:` line |
| MDC | `MDC:` line |
| MULTINODE | `Multinode:` line |
| REPLICATION | `Replication:` line |
| PARAM_ERROR_COUNT | Count of rows with `ERROR` status in parameter table |
| PARAM_ERROR_ROWS | file, section, parameter, detected value for each ERROR row |
| PARAM_STRICTNESS_ROWS | All rows with `OK (strictness high/low)` status |
| P1_SYSTEMDB | `P1 Alerts on SYSTEMDB on the last 40 days:` line |
| P1_TENANT | `P1 Alerts on the system <TENANT> on the last 40 days:` line |
| ALERT_DETAILS | Full PS4-ALERT DETAILS block — group by Alert ID, sum NUM_OF_EVENTS |
| TECH_TABLE_COUNT | `Big Technical Tables on <TENANT>:` line |
| TECH_TABLE_MEM_GB | First value in `Technical Tables usage in GB` line |
| TECH_TABLE_DISK_GB | Second value in `Technical Tables usage in GB` line |
| TECH_TABLE_LIST | All rows from `List of Technical Tables detected` block |
| LARGE_REC_SYSTEMDB | `Tables bigger than 1.5 billion records on SYSTEMDB:` line |
| LARGE_REC_TENANT | `Tables bigger than 1.5 billion records on <TENANT>:` line |
| OOM_SYSTEMDB | `OOM events on the last 40 days on SYSTEMDB:` line |
| OOM_TENANT | `OOM events on <TENANT> on the last 40 days:` line |
| MEM_ALLOCATED_GB | `ALL:` value in `MEMORY USED BY INDEXSERVER` line |
| MEM_USED_GB | `USE:` value in `MEMORY USED BY INDEXSERVER` line |
| ROWSTORE_ALL_GB | `ALL-` value in `ROWSTORE size (GB)` line |
| ROWSTORE_USE_GB | `USE-` value in `ROWSTORE size (GB)` line |
| COLSTORE_GB | `COLUMSTORE size` line value |
| TOP10_ALLOC_SYSTEMDB | Full `Top 10 Memory Allocators on SYSTEMDB` block |
| TOP10_ALLOC_TENANT | Full `Top 10 Memory Allocators on <TENANT>` block |
| HIGH_ALLOC_SYSTEMDB | `High Consuming Memory Allocators on SYSTEMDB` count |
| HIGH_ALLOC_TENANT | `High Consuming Memory Allocators on <TENANT>` count |
| PLAN_CACHE_LOW_EVENTS | `Plan Cache HIT Ratio on <TENANT> on the last 40 days:` line |
| PLAN_CACHE_DETAIL | `Low Cache HIT Ratio events` block |
| CPU_SPIKE_COUNT | `CPU spikes on the system on the last 40 days (95% threshold):` line |
| CPU_SPIKE_DETAIL | `CPU events higher than 95 percent` block |
| CPU_AVG | `CPU Average:` line |
| BLOCKED_TX | `Number of current Blocked Transactions on the system` line |
| BACKUP_FAILED | `Failed Backup executions on the last 40 days:` line (Y/N) |
| BACKUP_FAIL_DETAIL | Full `Failed Backup Execution details` block |
| LONG_RUNNING_BACKUPS | `Long Running Backups:` line |

---

### STEP 3 — Generate the HTML interactive report

Using all extracted data, generate a complete single-file HTML report following these EXACT requirements:

#### Style
- Color theme: Blue — primary `#0057a8`, dark `#003366`, accent `#00b4e6`, background `#e8f4fd`
- Header: Sticky, gradient blue, inline SVG SAP/HANA logo placeholder, all system metadata (SID, host, instance, tenant, version, cloud/type), colored environment badge
- Navigation: Sticky pill-bar below header with one link per section; scroll-spy highlighting; smooth scroll on click
- KPI summary cards: One card per major finding; color-coded red=danger, orange=warn, green=ok; clickable, scroll to relevant section
- Sections: Collapsible header (click to expand/collapse), icon, title, colored badge, chevron indicator
- Tables: Dark blue thead, alternating row shading, hover highlight pale blue, status pills, horizontal scroll wrapper
- Progress bars: Inline mini bar charts for disk GB columns (max value = 100%)
- Info boxes: Left-bordered colored boxes (blue/green/orange/red) for summaries
- Action items: Bulleted list with blue arrow markers
- Glossary tooltips: Every HANA technical term, table name, parameter name, alert ID, system view, INI file name wrapped in `<span class="term" data-term="KEY">`. On hover: fixed tooltip with title and definition. JS glossary object populated with ALL relevant terms from the data.
- Version banner: Wide gradient banner — installed version, SPS/revision, latest available (always compare to 2.00.089.00 / SPS08 Rev089 unless a newer one is known), match badge
- Footer: Centered, small font, SID, generation date, script version
- Responsive: Grid layouts use `auto-fill minmax()`
- No external dependencies: All CSS and JS inline, no CDN links

#### Sections to generate (always all 10, even if 0/none)

| # | Section | Icon | Content |
|---|---------|------|---------|
| 0 | Environment Summary | 🖥 | KPI cards + environment grid (SID, host, instance, cloud, CPU, RAM, volume, MDC, replication, memory usage with bar) |
| 1 | HANA Database Version | 🔢 | Version banner: installed vs latest, SPS/revision match badge, upgrade recommendation if behind |
| 2 | ECS Standard Parameters | ⚙ | Count ERROR/OK/OK-strictness; table of ERROR rows only; interpretation box; notable strictness deviations list |
| 3 | P1 Alerts – Last 40 Days | 🚨 | Count per DB; consolidated table grouped by Alert ID (sum NUM_OF_EVENTS); recommended actions |
| 4 | Big Technical Tables | 🗄 | Count, total memory GB, total disk GB; full table with schema, table, type, records, disk GB bar, mem GB, LOB flag, notes |
| 5 | Tables > 1.5 Billion Records | 📊 | Count; green box if 0; table if found |
| 6 | Out-of-Memory Events | 💾 | Count; memory utilisation grid (allocated, used, top allocators); preventive recommendations |
| 7 | CPU Spikes ≥ 95% | ⚡ | Count; table with timestamp, CPU%, bar; 40-day average; recommended actions |
| 8 | Failed Backups | 💿 | Count; danger box with pattern analysis (single-day vs spread, duration, affected DBs, retry loop); full detail table; recommended actions |
| 9 | Additional Risks | ⚠ | Table: risk area, observation, severity pill, recommended action — derived from all anomalies in the data |
|10 | Minichecks

	Analyze and check for what's abnormal, concerning or critical, create graphs for easy interpretation of results and sugest action item for:


		HANA_Resources_CPUAndMemory_2.00.060

          

		HANA_SQL_ExpensiveStatements_2.00.040+

		HANA_Tables_LargestTables_2.00.060+

		HANA_Configuration_Overview_2.00.080+

		HANA_Disks_Data_Partitions_2.00.040+

		HANA_IO_DiskDetails_2.00.020+

               
		HANA_IO_Savepoints_2.00.060+ |

#### Glossary — always define these terms (plus any additional ones found in the data)

SPS, Revision, PatchLevel, INIfile, ECS, global.ini, indexserver.ini, nameserver.ini,
sslminprotocolversion, Alert29, Alert39, Alert140, Mergedog, PlanViz, AdmissionControl,
TechnicalTable, NearlineStorage, AuditLogArchive, M_CS_TABLES, M_RS_TABLES, OOM,
M_DEV_MEMORY_COMPONENT_ALLOCATORS, M_LOAD_HISTORY_SERVICE, WorkloadClass,
StatementTimeout, Backint, PlanCacheHitRatio, PlanStability, DisasterRecoveryPrimary,
TLSProtocol, DeltaMerge, SOFFCONT1, REPOLOAD, RSAU_LOG, REPOSRC, EDID4,
OBJECT_HISTORY, DBTABLOG, SWWCNTP0, CDPOS, BALDAT, D010TAB,
M_BACKUP_CATALOG, M_SQL_PLAN_CACHE, M_SERVICE_REPLICATION,
M_OUT_OF_MEMORY_EVENTS, M_BLOCKED_TRANSACTIONS

#### Output format
- Single `.html` file, no external resources
- All CSS in `<style>` block in `<head>`
- All JS in `<script>` block before `</body>`
- No HTML comments, no text outside HTML tags

Save the HTML file as:
`C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory\<DB_NAME>_health_check_report.html`

---

### STEP 4 — Generate the Excel Python script and run it

Generate a single self-contained Python script using `openpyxl`. No comments, no docstrings, no markdown fences. Proper 4-space indentation. No raw newlines inside string literals.

#### 9 Observation rows — compose one executive paragraph per row:

| Row | Item Title | Observation rules |
|---|---|---|
| 1 | HANA Database Version | State installed version + SPS/revision. Compare to latest (2.00.089.00 / SPS08 Rev089). If match: no upgrade needed, monitor future. If behind: state gap, recommend upgrade planning. |
| 2 | ECS Standard Parameter Compliance | State ERROR count. Name each ERROR parameter (file, section, name, detected value). Explain impact. State all others compliant. Recommend exception documentation or remediation via UNSET. |
| 3 | P1 Alerts – Last 40 Days | State total per DB. Group by Alert ID. For each: name, total events, key finding (max delta size for Alert29, max runtime for Alert39, license state for Alert140). Recommend action per alert type. |
| 4 | Big Technical Tables – Memory and Disk | State count, total mem GB, total disk GB. Name top 5 by disk: table, disk GB, records, category. State archiving program per table type. Recommend monthly M_CS_TABLES review. |
| 5 | Tables or Partitions Exceeding 1.5 Billion Records | If 0: positive finding, name tables approaching threshold, recommend M_CS_TABLES monitoring. If found: name each, recommend partitioning strategy review. |
| 6 | Out-of-Memory (OOM) Events | If 0: positive finding. State mem utilisation (used/allocated/physical). Name top 1-2 allocators with GB and %. Recommend global_allocation_limit review, archiving, weekly monitoring. If events: state count/date/service, recommend OOM dump analysis. |
| 7 | Top 10 Tables with Highest Transaction Activity | Note if dedicated DML query not in script. Derive from available data: tables with highest write indicators. Recommend M_TABLE_STATISTICS / M_CS_TABLES with WRITE_COUNT/UPDATE_COUNT filter. |
| 8 | CPU Spikes | State count and threshold. For each spike: timestamp and CPU%. State 40-day average. Correlate with long-running statements if timestamps align. Recommend M_LOAD_HISTORY_SERVICE, statement optimization, StatementTimeout, WorkloadClasses. |
| 9 | Failed Backups | State total count. Identify date(s). State affected DBs. Describe duration pattern (immediate rejection vs timeout). Identify retry loop if SYSTEMDB shows multiple per hour. Recommend: confirm successful backup exists after failure, investigate Backint/storage logs, correct retry config, implement M_BACKUP_CATALOG monitoring. |

#### Excel formatting

```
Filename : HANA_health_check_summary_observations_<DB_NAME>.xlsx
Worksheet: HANA Health Check Analysis
```

Columns (left to right): Item Num | Type | Priority | Item | Observations | System | Responsible | Link to section
Column widths: 10 | 12 | 12 | 60 | 90 | 12 | 20 | 18

- Row 1 (Caption): "DB Health check summary" — Bold 14pt black, Orange fill FFA500, merged A1:H1, centered, height 28, thick outer border
- Row 2 (Header): Bold 10pt white, fill 1F497D, centered + wrap, height 22
- Rows 3-11 (Data): Calibri 10pt, left+top+wrap; Item Num/Type/Priority/System/Responsible centered; alternating white FFFFFF (odd) / light blue EBF3FB (even); height 120
- Static values: Type="Database", Priority="Medium", System=DB_NAME, Responsible="Customer / TSM", Link to section=blank
- Borders: caption thick outer; header+data block medium outer edges, thin inner
- Freeze panes at A3
- End with `wb.save(FILE_NAME)` and `print(f"File saved: {FILE_NAME}")`

Save the Python script as:
`C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory\HANA_health_check_<DB_NAME>.py`

Then execute it with:
```bash
cd "C:\Users\I522148\OneDrive - SAP SE\SWAT\AI\Claude\working directory" && python HANA_health_check_<DB_NAME>.py
```

---

### STEP 5 — Move both output files to the customer folder

Create the destination folder if it does not exist:
`C:\Users\I522148\OneDrive - SAP SE\SWAT\PLAs\Q2-H2\<CUSTOMER_NAME>\`

Move both files:
- `<DB_NAME>_health_check_report.html`
- `HANA_health_check_summary_observations_<DB_NAME>.xlsx`

To:
`C:\Users\I522148\OneDrive - SAP SE\SWAT\PLAs\Q2-H2\<CUSTOMER_NAME>\`

Confirm with a directory listing of the destination folder.

---

## [PASTE FILENAME AND CUSTOMER NAME AT THE TOP OF THIS PROMPT BEFORE SENDING]
