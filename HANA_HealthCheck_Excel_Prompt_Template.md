# SAP HANA Health Check – Excel Report Generation Prompt

---

## HOW TO USE THIS TEMPLATE

1. Run the HANA Health Check script on the target system
2. Copy the full script output (from `[SCRIPT-Info]` lines through the parameter table)
3. Paste it into the **[PASTE HEALTH CHECK OUTPUT HERE]** section below
4. Send the entire prompt to Claude — it will output ready-to-execute Python code
5. Save the code as a `.py` file and run it with `python <filename>.py`
6. Requires: `pip install openpyxl`

---

## PROMPT (copy everything below this line)

---

From the following SAP HANA database health check output, generate FULL INDENTED Python code READY TO EXECUTE with NO COMMENTS OR ANYTHING NOT RELEVANT to create an Excel spreadsheet. The code must be clean, properly indented, and careful with line breaks inside strings.

---

### STEP 1 — EXTRACT FROM THE DATA

Before writing any code, extract the following values from the pasted health check output:

| Variable | Where to find it | Example |
|---|---|---|
| `DB_NAME` | `SID:` line in `[environment]` section | `HP4` |
| `DB_VERSION` | `HDB version:` line | `2.00.089.00` |
| `LATEST_VERSION` | Always `2.00.089.00` (SPS08 Rev 089) unless a newer one is stated | `2.00.089.00` |
| `TENANT_NAME` | Prefix used in metric lines (e.g. `PS4-COLUMSTORE`) or backup DB names | `PS4` |
| `HOST` | `Installationname:` line | `vhreyhp4db01` |
| `CLOUD` | `Cloud:` line | `AZURE` |
| `CPU_PHYS` | `CPU_PHYS:` line | `16` |
| `PHYS_MEM` | `PHYS_MEM:` line | `251` |
| `VOLUME` | `Volume Size:` line | `460G` |
| `REPLICATION` | `Replication:` line | `primary` |
| `PARAM_ERROR_COUNT` | Count of rows with `ERROR` status in the parameter table | `2` |
| `PARAM_ERROR_ROWS` | List of: file, section, parameter, detected value for each ERROR row | see data |
| `P1_SYSTEMDB` | `P1 Alerts on SYSTEMDB on the last 40 days:` line | `0` |
| `P1_TENANT` | `P1 Alerts on the system <TENANT> on the last 40 days:` line | `304` |
| `ALERT_SUMMARY` | Group alert rows by Alert ID, sum NUM_OF_EVENTS, keep top alert detail per group | see data |
| `TECH_TABLE_COUNT` | `Big Technical Tables on <TENANT>:` line | `17` |
| `TECH_TABLE_MEM_GB` | First value in `Technical Tables usage in GB` line | `28.85` |
| `TECH_TABLE_DISK_GB` | Second value in `Technical Tables usage in GB` line | `188.19` |
| `TECH_TABLE_LIST` | Top tables parsed from `List of Technical Tables detected` — name, disk GB, mem GB, records | see data |
| `LARGE_REC_SYSTEMDB` | `Tables bigger than 1.5 billion records on SYSTEMDB:` line | `0` |
| `LARGE_REC_TENANT` | `Tables bigger than 1.5 billion records on <TENANT>:` line | `0` |
| `OOM_SYSTEMDB` | `OOM events on the last 40 days on SYSTEMDB:` line | `0` |
| `OOM_TENANT` | `OOM events on <TENANT> on the last 40 days:` line | `0` |
| `TOP10_ALLOCATORS_TENANT` | `Top 10 Memory Allocators on <TENANT>` — top 3 by percent | see data |
| `MEM_ALLOCATED_GB` | First value `ALL:` in `MEMORY USED BY INDEXSERVER` | `194.800` |
| `MEM_USED_GB` | Second value `USE:` in `MEMORY USED BY INDEXSERVER` | `157.560` |
| `PLAN_CACHE_LOW_EVENTS` | `Plan Cache HIT Ratio on <TENANT> on the last 40 days:` line | `10` |
| `CPU_SPIKE_COUNT` | `CPU spikes on the system on the last 40 days (95% threshold):` line | `1` |
| `CPU_SPIKE_DETAIL` | Rows from `CPU events higher than 95 percent` | `2026-06-24 09:16:14, 95%` |
| `CPU_AVG` | `CPU Average:` line | `0.620797` |
| `BACKUP_FAILED` | `Failed Backup executions on the last 40 days:` line (`Y`/`N`) | `Y` |
| `BACKUP_FAIL_COUNT` | Count of rows in `Failed Backup Execution details` block | `24` |
| `BACKUP_FAIL_DETAIL` | Parse: affected DBs, date(s), duration pattern, type | see data |

---

### STEP 2 — BUILD 9 OBSERVATION ROWS

Using the extracted values, compose one executive-language paragraph per row.
Rules:
- One paragraph per section — no bullet lists, no raw SQL, no parameter dumps
- Include: current situation + key risk or finding + recommended direction
- Use numbers and specifics from the extracted data
- Management/executive tone

| Row | Item title | Observation content rules |
|---|---|---|
| 1 | HANA Database Version | State installed version, SPS/revision, compare to latest (2.00.089.00 / SPS08 Rev 089). If match: no upgrade needed, monitor future revisions. If behind: state the gap and recommend upgrade planning. |
| 2 | ECS Standard Parameter Compliance | State total ERROR count. Name each ERROR parameter (file, section, parameter, detected value). Explain impact. State all other parameters are compliant. Recommend exception documentation or remediation. |
| 3 | P1 Alerts – Last 40 Days | State total count per DB. Group by Alert ID. For each group: name, total events, key finding (e.g. max delta size for Alert 29, max runtime for Alert 39, license state for Alert 140). State recommended action per alert type. |
| 4 | Big Technical Tables – Memory and Disk Consumption | State count, total mem GB, total disk GB. Name top 5 by disk. For each: table name, disk GB, record count, category. State archiving program or SAP transaction per table type. Recommend monthly M_CS_TABLES review. |
| 5 | Tables or Partitions Exceeding 1.5 Billion Records | If 0: positive finding, name any tables approaching threshold from tech table list, recommend monitoring via M_CS_TABLES. If found: name each table/partition and record count, recommend partitioning strategy review. |
| 6 | Out-of-Memory (OOM) Events | If 0: positive finding. State memory utilisation numbers (used/allocated/physical). Name top 1-2 allocators with GB and %. State preventive recommendations (global_allocation_limit, archiving, weekly monitoring). If events found: state count, date, service, recommend OOM dump analysis. |
| 7 | Top 10 Tables with Highest Transaction Activity | Note if a dedicated top-10 DML query was not included in this script execution. Derive from available data: list tables with highest write indicators (delta backlog, high row count, IDoc/log/workflow nature). Recommend running M_TABLE_STATISTICS / M_CS_TABLES with WRITE_COUNT / UPDATE_COUNT filter. |
| 8 | CPU Spikes | State spike count and threshold (95%). For each spike: timestamp and CPU%. State 40-day average. Correlate with long-running statement if timestamps align. Recommend: M_LOAD_HISTORY_SERVICE correlation, statement optimization, statement timeout parameter, Workload Classes. |
| 9 | Failed Backups | State total failure count. Identify date(s) affected. State affected DBs. Describe duration pattern (immediate rejection vs timeout). Identify retry loop pattern if SYSTEMDB shows multiple attempts per hour. Recommend: confirm successful backup exists after failure date, investigate Backint/storage logs, correct retry config, implement monitoring alerts. |
|10 | Minichecks

	Analyze and check for what's abnormal, concerning or critical, sugest action item for:


		HANA_Resources_CPUAndMemory_2.00.060

		HANA_SQL_ExpensiveStatements_2.00.040+

		HANA_Tables_LargestTables_2.00.060+

		HANA_Configuration_Overview_2.00.080+

		HANA_Disks_Data_Partitions_2.00.040+

		HANA_IO_DiskDetails_2.00.020+


		HANA_IO_Savepoints_2.00.060+ |

### STEP 3 — GENERATE THE PYTHON CODE

Generate a single self-contained Python script using `openpyxl`. No comments. No explanatory text. Only executable Python code.

#### File and sheet

```
filename : HANA_health_check_summary_observations_<DB_NAME>.xlsx
worksheet: HANA Health Check Analysis
```

#### Columns (left to right, exactly in this order)

| # | Column name | Content rule |
|---|---|---|
| 1 | Item Num | Sequential integers starting at 1 |
| 2 | Type | Static value: `Database` |
| 3 | Priority | Static value: `Medium` |
| 4 | Item | Section title from row definitions above |
| 5 | Observations | Executive paragraph from row definitions above |
| 6 | System | `<DB_NAME>` extracted from the data |
| 7 | Responsible | Static value: `Customer / TSM` |
| 8 | Link to section | Leave blank |

Total columns: 8

#### Caption row (row 1)

- Text: `DB Health check summary`
- Font: Bold, 14pt, black
- Alignment: Horizontally and vertically centered
- Background: Orange (`FFA500`)
- Merged across all 8 columns
- Row height: 28

#### Header row (row 2)

- Font: Bold, 10pt, white
- Fill: Dark blue (`1F497D`)
- Alignment: Center horizontally and vertically, wrap text
- Row height: 22

#### Data rows (rows 3 onward)

- Font: Calibri 10pt
- Alignment: Left, vertical top, wrap text enabled on all cells
- Item Num, Type, Priority, System, Responsible: horizontally centered
- Alternating row fill: white (`FFFFFF`) for odd rows, light blue (`EBF3FB`) for even rows
- Row height: 120

#### Column widths

| Column | Width (chars) |
|---|---|
| Item Num | 10 |
| Type | 12 |
| Priority | 12 |
| Item | 60 |
| Observations | 90 |
| System | 12 |
| Responsible | 20 |
| Link to section | 18 |

#### Borders

- Draw borders around the full table (header row through last data row)
- Outer edges (top, bottom, left, right of the entire table): thick / medium sides
- Inner cell borders: thin sides
- Caption row: thick outer border on all 4 sides

#### Additional

- Freeze panes at A3 (header row always visible)
- End with `wb.save(FILE_NAME)` and `print(f"File saved: {FILE_NAME}")`

---

### STEP 4 — OUTPUT FORMAT RULES

- Output ONLY the Python code — nothing before, nothing after
- No markdown code fences
- No inline comments
- No docstrings
- Proper 4-space indentation throughout
- No line inside a string literal may contain a raw newline — use string concatenation (`+`) or implicit continuation across lines if an observation paragraph is long
- All string values for the `rows` list must be written as a single expression per cell — no multiline triple-quoted strings that depend on indentation

---

## [PASTE HEALTH CHECK OUTPUT HERE]

```
<<< REPLACE THIS LINE WITH THE FULL HANA HEALTH CHECK SCRIPT OUTPUT >>>
```

---
