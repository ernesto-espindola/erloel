# HANA Health Check – SQL Query Reference
**Script:** `HanaHealthCheck.sh` v1.033  
**Last Updated:** 2024-07-29  
**Purpose:** Lists every SQL query executed by the script, with the execution target (SYSTEMDB, Tenant DB, or Both) and the purpose of each query.

---

## Quick Reference Table

| # | Function | Query | Target DB | Purpose |
|---|----------|-------|-----------|---------|
| 1 | fct_get_tenants | SELECT DATABASE_NAME FROM M_DATABASES | **SYSTEMDB** | Discover active tenant databases |
| 2 | fct_check_backups – Q1 | COUNT failed backups | **SYSTEMDB** | Detect failed backup executions |
| 3 | fct_check_backups – Q2 | Detail of failed backups | **SYSTEMDB** | List failed backup details |
| 4 | fct_check_backups – Q3 | COUNT slow backups | **SYSTEMDB** | Detect below-average-speed backups |
| 5 | fct_check_backups – Q4 | Detail of slow backups | **SYSTEMDB** | List slow backup details |
| 6 | fct_check_memory – Q1 | COUNT high nameserver allocators | **SYSTEMDB** | Detect nameserver memory pressure (>30%) |
| 7 | fct_check_memory – Q2 | Top 10 nameserver allocators detail | **SYSTEMDB** | Show top memory consumers in nameserver |
| 8 | fct_check_memory – Q3 | COUNT OOM events (SYSTEMDB) | **SYSTEMDB** | Detect OOM trace files (last 40 days) |
| 9 | fct_check_memory – Q4 | OOM event file detail (SYSTEMDB) | **SYSTEMDB** | List OOM trace file names and timestamps |
| 10 | fct_check_store_areas – Q1 | Rowstore allocated vs. in-use | **Tenant DB** | Rowstore memory footprint (GB) |
| 11 | fct_check_store_areas – Q2 | Columnstore estimated max memory | **Tenant DB** | Columnstore memory footprint (GB) |
| 12 | fct_check_store_areas – Q3 | Indexserver heap + shared memory | **Tenant DB** | Total indexserver memory (GB) |
| 13 | fct_check_cpu – Q1 | COUNT CPU spikes ≥95% | **Tenant DB** | Detect CPU spike events (last 40 days) |
| 14 | fct_check_cpu – Q2 | CPU average | **Tenant DB** | Average CPU utilization (last 40 days) |
| 15 | fct_check_cpu – Q3 | CPU spike detail (top 100) | **Tenant DB** | List timestamps and CPU values per spike |
| 16 | fct_check_block_transactions – Q1 | COUNT blocked transactions | **Tenant DB** | Detect current blocked transactions |
| 17 | fct_check_block_transactions – Q2 | Blocked transactions detail | **Tenant DB** | List lock owner, blocked statement, wait info |
| 18 | fct_check_ttables – Q1 | COUNT technical tables > 1 GB | **Tenant DB** | Count oversized technical tables |
| 19 | fct_check_ttables – Q2 | Technical tables full detail list | **Tenant DB** | Full table size report (disk, mem, LOBs, indexes) |
| 20 | fct_check_ttables – Q3 | Technical tables total mem+disk (GB) | **Tenant DB** | Aggregate memory and disk used by tech tables |
| 21 | fct_check_memory – Q5 | COUNT plan cache low hit ratio events | **Tenant DB** | Detect plan cache hit ratio < 90% (last 40 days) |
| 22 | fct_check_memory – Q6 | Plan cache low hit ratio detail | **Tenant DB** | List snapshots with low hit ratio |
| 23 | fct_check_memory – Q7 | COUNT high indexserver allocators | **Tenant DB** | Detect indexserver memory pressure (>30%) |
| 24 | fct_check_memory – Q8 | Top 10 indexserver allocators detail | **Tenant DB** | Show top memory consumers in indexserver |
| 25 | fct_check_memory – Q9 | COUNT OOM events (Tenant) | **Tenant DB** | Detect OOM trace files per tenant (last 40 days) |
| 26 | fct_check_memory – Q10 | OOM event file detail (Tenant) | **Tenant DB** | List OOM trace file names and timestamps |
| 27 | fct_check_alerts – Q1 | COUNT P1 alerts | **Both** | Count P1 alerts (last 40 days, excl. 17/22/23/24) |
| 28 | fct_check_alerts – Q2 | P1 alert detail (top 100) | **Both** | List alert IDs, ratings, and details |
| 29 | fct_check_bigtables – Q1 | COUNT tables > 1.5 B records | **Both** | Detect column store tables with excessive rows |
| 30 | fct_check_bigtables – Q2 | Big tables detail | **Both** | List schema, table, partition, record count |
| 31 | fct_check_hdbuserstore_* | SELECT * FROM DUMMY | **Both** | HDBuilderstore connection validation |

---

## SYSTEMDB-Only Queries

> These queries use cross-database views (`SYS_DATABASES.*`) or retrieve system-level metadata that is only available from the SYSTEMDB connection.

---

### Q1 – Tenant Discovery
**Function:** `fct_get_tenants`  
**Connection key:** `STDMUSER` (SYSTEMDB)

```sql
SELECT DATABASE_NAME
FROM M_DATABASES
WHERE DESCRIPTION NOT LIKE '%SystemDB%'
  AND ACTIVE_STATUS = 'YES'
```

---

### Q2 – Count of Failed Backup Executions (last 40 days)
**Function:** `fct_check_backups` – sqlstmt  
**Connection key:** `STDMUSER` (SYSTEMDB)

```sql
SELECT COUNT(1)
FROM (
  SELECT COUNT(1)
  FROM SYS_DATABASES.M_BACKUP_CATALOG A
  WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
    AND A.STATE_NAME NOT IN ('successful', 'running')
  GROUP BY A.ENTRY_TYPE_NAME, A.STATE_NAME
)
```

---

### Q3 – Failed Backup Details
**Function:** `fct_check_backups` – sqlstmt1  
**Connection key:** `STDMUSER` (SYSTEMDB)  
*Runs only when Q2 returns > 0*

```sql
SELECT
  A.DATABASE_NAME,
  A.ENTRY_TYPE_NAME,
  TO_CHAR(A.SYS_START_TIME, 'dd/mm/yyyy hh24:mi:ss') AS START_DATE,
  TO_CHAR(A.SYS_END_TIME,   'dd/mm/yyyy hh24:mi:ss') AS END_DATE,
  A.STATE_NAME
FROM SYS_DATABASES.M_BACKUP_CATALOG A
WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
  AND A.STATE_NAME NOT IN ('successful', 'running')
```

---

### Q4 – Count of Slow (Below-Average) Backups
**Function:** `fct_check_backups` – sqlstmt2  
**Connection key:** `STDMUSER` (SYSTEMDB)

```sql
SELECT COUNT(1) FROM (
  SELECT TOP 10
    A.ENTRY_TYPE_NAME,
    TO_CHAR(A.SYS_START_TIME, 'dd/mm/yyyy hh24:mi:ss') AS START_DATE,
    TO_CHAR(A.SYS_END_TIME,   'dd/mm/yyyy hh24:mi:ss') AS END_DATE,
    SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60                         AS DURATION_MINS,
    (SELECT AVG(SECONDS_BETWEEN(SYS_START_TIME, SYS_END_TIME) / 60)
     FROM SYS_DATABASES.M_BACKUP_CATALOG
     WHERE ENTRY_TYPE_NAME NOT LIKE '%log%')                                         AS AVG_DURATION_MINS,
    A.STATE_NAME,
    B.BACKUP_SIZE / 1024 / 1024                                                      AS BACKUP_GB,
    (B.BACKUP_SIZE / 1024 / 1024) / (SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60) AS GB_PER_MIN,
    (SELECT AVG((B.BACKUP_SIZE / 1024 / 1024) / SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60)
     FROM SYS_DATABASES.M_BACKUP_CATALOG A
     JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
           FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
           WHERE SOURCE_TYPE_NAME = 'volume'
           GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
     WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
       AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) > '0')                AS AVG_GB_PER_MIN
  FROM SYS_DATABASES.M_BACKUP_CATALOG A
  JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
        FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
        WHERE SOURCE_TYPE_NAME = 'volume'
        GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
  WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
    AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) != '0'
    AND (B.BACKUP_SIZE / 1024 / 1024) / (SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60) <
        (SELECT AVG((B.BACKUP_SIZE / 1024 / 1024) / SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60)
         FROM SYS_DATABASES.M_BACKUP_CATALOG A
         JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
               FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
               WHERE SOURCE_TYPE_NAME = 'volume'
               GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
         WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
           AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) > '0')
  ORDER BY 7 ASC
)
```

---

### Q5 – Slow Backup Details (Top 10)
**Function:** `fct_check_backups` – sqlstmt3  
**Connection key:** `STDMUSER` (SYSTEMDB)  
*Runs only when Q4 returns > 0*

```sql
SELECT TOP 10
  A.DATABASE_NAME,
  A.ENTRY_TYPE_NAME,
  TO_CHAR(A.SYS_START_TIME, 'dd/mm/yyyy hh24:mi:ss') AS START_DATE,
  TO_CHAR(A.SYS_END_TIME,   'dd/mm/yyyy hh24:mi:ss') AS END_DATE,
  SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60                         AS DURATION_MINS,
  (SELECT AVG(SECONDS_BETWEEN(SYS_START_TIME, SYS_END_TIME) / 60)
   FROM SYS_DATABASES.M_BACKUP_CATALOG
   WHERE ENTRY_TYPE_NAME NOT LIKE '%log%')                                         AS AVG_DURATION_MINS,
  A.STATE_NAME,
  B.BACKUP_SIZE / 1024 / 1024                                                      AS BACKUP_GB,
  (B.BACKUP_SIZE / 1024 / 1024) / (SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60) AS GB_PER_MIN,
  (SELECT AVG((B.BACKUP_SIZE / 1024 / 1024) / SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60)
   FROM SYS_DATABASES.M_BACKUP_CATALOG A
   JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
         FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
         WHERE SOURCE_TYPE_NAME = 'volume'
         GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
   WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
     AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) > '0')                AS AVG_GB_PER_MIN
FROM SYS_DATABASES.M_BACKUP_CATALOG A
JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
      FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
      WHERE SOURCE_TYPE_NAME = 'volume'
      GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
  AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) > '0'
  AND (B.BACKUP_SIZE / 1024 / 1024) / (SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60) <
      (SELECT AVG((B.BACKUP_SIZE / 1024 / 1024) / SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) / 60)
       FROM SYS_DATABASES.M_BACKUP_CATALOG A
       JOIN (SELECT BACKUP_ID, SUM(BACKUP_SIZE) / 1024 AS BACKUP_SIZE
             FROM SYS_DATABASES.M_BACKUP_CATALOG_FILES
             WHERE SOURCE_TYPE_NAME = 'volume'
             GROUP BY BACKUP_ID) B ON A.BACKUP_ID = B.BACKUP_ID
       WHERE A.ENTRY_TYPE_NAME NOT LIKE '%log%'
         AND SECONDS_BETWEEN(A.SYS_START_TIME, A.SYS_END_TIME) > '0')
ORDER BY BACKUP_GB ASC
```

---

### Q6 – Count of High Memory Allocators on Nameserver (>30% of total)
**Function:** `fct_check_memory` – sqlstmt2a  
**Connection key:** `STDMUSER` (SYSTEMDB)

```sql
SELECT COUNT(1) FROM (
  SELECT TOP 10
    M_SERVICES.HOST,
    M_SERVICES.SERVICE_NAME,
    M_HEAP_MEMORY.CATEGORY,
    M_HEAP_MEMORY.INCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS INCLUSIVE_SIZE_IN_USE,
    M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS EXCLUSIVE_SIZE_IN_USE,
    ROUND(
      (M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024) /
      (SELECT TOP 1 ROUND((HEAP_MEMORY_ALLOCATED_SIZE + SHARED_MEMORY_USED_SIZE) / 1024 / 1024 / 1024, 2)
       FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY
       WHERE SERVICE_NAME = 'nameserver'
         AND HOST IN (SELECT HOST FROM M_SERVICES WHERE COORDINATOR_TYPE = 'MASTER' AND SERVICE_NAME = 'nameserver')
       ORDER BY SNAPSHOT_ID DESC) * 100, 2) AS PERCENT_FROM_TOTAL
  FROM M_HEAP_MEMORY, M_SERVICES
  WHERE M_HEAP_MEMORY.PORT  = M_SERVICES.PORT
    AND M_HEAP_MEMORY.HOST  = M_SERVICES.HOST
    AND M_SERVICES.SERVICE_NAME = 'nameserver'
  ORDER BY M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE DESC
)
WHERE PERCENT_FROM_TOTAL > 30
```

---

### Q7 – Top 10 Nameserver Memory Allocators (Detail)
**Function:** `fct_check_memory` – sqlstmt3a  
**Connection key:** `STDMUSER` (SYSTEMDB)  
*Runs only when Q6 returns > 0*

```sql
SELECT TOP 10
  M_SERVICES.HOST,
  M_SERVICES.SERVICE_NAME,
  M_HEAP_MEMORY.CATEGORY,
  M_HEAP_MEMORY.INCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS INCLUSIVE_SIZE_IN_USE,
  M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS EXCLUSIVE_SIZE_IN_USE,
  ROUND(
    (M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024) /
    (SELECT TOP 1 ROUND((HEAP_MEMORY_ALLOCATED_SIZE + SHARED_MEMORY_USED_SIZE) / 1024 / 1024 / 1024, 2)
     FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY
     WHERE SERVICE_NAME = 'nameserver'
       AND HOST IN (SELECT HOST FROM M_SERVICES WHERE COORDINATOR_TYPE = 'MASTER' AND SERVICE_NAME = 'nameserver')
     ORDER BY SNAPSHOT_ID DESC) * 100, 2) AS PERCENT_FROM_TOTAL
FROM M_HEAP_MEMORY, M_SERVICES
WHERE M_HEAP_MEMORY.PORT  = M_SERVICES.PORT
  AND M_HEAP_MEMORY.HOST  = M_SERVICES.HOST
  AND M_SERVICES.SERVICE_NAME = 'nameserver'
ORDER BY M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE DESC
```

---

### Q8 – Count of OOM Trace Files on SYSTEMDB (last 40 days)
**Function:** `fct_check_memory` – sqlstmt4 (SYSTEMDB run)  
**Connection key:** `STDMUSER` (SYSTEMDB)

```sql
SELECT COUNT(1) FROM (
  SELECT *
  FROM M_TRACEFILES
  WHERE SECONDS_BETWEEN(FILE_MTIME, CURRENT_TIMESTAMP) <= 3456000
    AND FILE_NAME LIKE '%oom%'
)
```

---

### Q9 – OOM Trace File Details on SYSTEMDB (Top 50)
**Function:** `fct_check_memory` – sqlstmt5 (SYSTEMDB run)  
**Connection key:** `STDMUSER` (SYSTEMDB)  
*Runs only when Q8 returns > 0*

```sql
SELECT TOP 50 FILE_NAME, FILE_MTIME
FROM M_TRACEFILES
WHERE SECONDS_BETWEEN(FILE_MTIME, CURRENT_TIMESTAMP) <= 3456000
  AND FILE_NAME LIKE '%oom%'
ORDER BY FILE_MTIME DESC
```

---

## Tenant DB-Only Queries

> These queries are executed per-tenant database using the `STDMUSER<TENANT>` hdbuserstore key. SYSTEMDB is always skipped in the loop.

---

### Q10 – Rowstore Allocated vs. In-Use (GB)
**Function:** `fct_check_store_areas` – sqlstmt  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT MEMORY_ALLOCATED, MEMORY_IN_USE
FROM (
  SELECT TOP 1
    SNAPSHOT_ID,
    'ALL-' || TO_DECIMAL(ROUND(SUM(ALLOCATED_FIXED_PART_SIZE + ALLOCATED_VARIABLE_PART_SIZE) / 1024 / 1024 / 1024, 3), 34, 3) AS MEMORY_ALLOCATED,
    'USE-' || TO_DECIMAL(ROUND(SUM(USED_FIXED_PART_SIZE     + USED_VARIABLE_PART_SIZE)     / 1024 / 1024 / 1024, 3), 34, 3) AS MEMORY_IN_USE
  FROM _SYS_STATISTICS.GLOBAL_ROWSTORE_TABLES_SIZE
  WHERE SCHEMA_NAME NOT IN ('SYS')
  GROUP BY SNAPSHOT_ID
  ORDER BY SNAPSHOT_ID DESC
)
```

---

### Q11 – Columnstore Estimated Max Memory (GB)
**Function:** `fct_check_store_areas` – sqlstmt2  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT MEMORY_USED
FROM (
  SELECT TOP 1
    SNAPSHOT_ID,
    TO_DECIMAL(ROUND(SUM(ESTIMATED_MAX_MEMORY_SIZE_IN_TOTAL / 1024 / 1024 / 1024), 2), 34, 3) AS MEMORY_USED
  FROM _SYS_STATISTICS.HOST_COLUMN_TABLES_PART_SIZE
  WHERE SCHEMA_NAME NOT IN ('_SYS_REPO', '_SYS_STATISTICS')
  GROUP BY SNAPSHOT_ID
  ORDER BY SNAPSHOT_ID DESC
)
```

---

### Q12 – Indexserver Heap + Shared Memory (GB)
**Function:** `fct_check_store_areas` – sqlstmt3  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT TOP 1
  'ALL:' || TO_DECIMAL(ROUND((HEAP_MEMORY_ALLOCATED_SIZE + SHARED_MEMORY_ALLOCATED_SIZE) / 1024 / 1024 / 1024, 2), 34, 3) AS ALLOCATED,
  'USE:' || TO_DECIMAL(ROUND((HEAP_MEMORY_USED_SIZE      + SHARED_MEMORY_USED_SIZE)      / 1024 / 1024 / 1024, 2), 34, 3) AS IN_USE
FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY
WHERE SERVICE_NAME = 'indexserver'
  AND HOST IN (
    SELECT HOST FROM M_SERVICES
    WHERE COORDINATOR_TYPE = 'MASTER' AND SERVICE_NAME = 'indexserver'
  )
ORDER BY SNAPSHOT_ID DESC
```

---

### Q13 – Count of CPU Spike Events ≥95% (last 40 days)
**Function:** `fct_check_cpu` – sqlstmt  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) AS EVENTS
FROM (
  SELECT TIME, CPU
  FROM _SYS_STATISTICS.HOST_LOAD_HISTORY_SERVICE
  WHERE SECONDS_BETWEEN(TIME, CURRENT_TIMESTAMP) <= 3456000
    AND CPU >= 95
)
```

---

### Q14 – Average CPU Utilization (last 40 days)
**Function:** `fct_check_cpu` – sqlstmt2  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT AVG(CPU) AS CPU_AVERAGE
FROM _SYS_STATISTICS.HOST_LOAD_HISTORY_SERVICE
WHERE SECONDS_BETWEEN(TIME, CURRENT_TIMESTAMP) <= 3456000
```

---

### Q15 – CPU Spike Event Detail (Top 100, last 40 days)
**Function:** `fct_check_cpu` – sqlstmt3  
**Connection key:** `STDMUSER<TENANT>`  
*Runs only when Q13 returns > 0*

```sql
SELECT TOP 100 TIME, CPU
FROM _SYS_STATISTICS.HOST_LOAD_HISTORY_SERVICE
WHERE SECONDS_BETWEEN(TIME, CURRENT_TIMESTAMP) <= 3456000
  AND CPU >= 95
ORDER BY TIME DESC
```

---

### Q16 – Count of Current Blocked Transactions
**Function:** `fct_check_block_transactions` – sqlstmt  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) AS NUM_OF_BLOCKED_TRANSACTIONS
FROM SYS.M_BLOCKED_TRANSACTIONS B
JOIN SYS.M_TRANSACTIONS T
  ON (B.HOST, B.PORT, B.LOCK_OWNER_TRANSACTION_ID) = (T.HOST, T.PORT, T.TRANSACTION_ID)
LEFT OUTER JOIN SYS.M_TRANSACTIONS TP
  ON (T.VOLUME_ID, T.PRIMARY_TRANSACTION_ID) = (TP.VOLUME_ID, TP.TRANSACTION_ID)
  AND TP.TRANSACTION_TYPE = 'USER TRANSACTION'
JOIN SYS.M_CONNECTIONS C
  ON MAP(TP.CONNECTION_ID, NULL, T.CONNECTION_ID, TP.CONNECTION_ID) = C.CONNECTION_ID
JOIN SYS.M_TRANSACTIONS TB
  ON (B.HOST, B.PORT, B.BLOCKED_TRANSACTION_ID) = (TB.HOST, TB.PORT, TB.TRANSACTION_ID)
LEFT OUTER JOIN SYS.M_TRANSACTIONS TBP
  ON (TB.VOLUME_ID, TB.PRIMARY_TRANSACTION_ID) = (TBP.VOLUME_ID, TBP.TRANSACTION_ID)
  AND TBP.TRANSACTION_TYPE = 'USER TRANSACTION'
JOIN SYS.M_CONNECTIONS CB
  ON MAP(TBP.CONNECTION_ID, NULL, TB.CONNECTION_ID, TBP.CONNECTION_ID) = CB.CONNECTION_ID
LEFT OUTER JOIN SYS.M_ACTIVE_STATEMENTS P
  ON CB.CURRENT_STATEMENT_ID = P.STATEMENT_ID
```

---

### Q17 – Blocked Transactions Detail
**Function:** `fct_check_block_transactions` – sqlstmt2  
**Connection key:** `STDMUSER<TENANT>`  
*Runs only when Q16 returns > 0*

```sql
SELECT
  B.HOST, B.PORT,
  B.BLOCKED_TRANSACTION_ID,
  MAP(TP.CONNECTION_ID, NULL, T.CONNECTION_ID, TP.CONNECTION_ID) AS LOCK_OWNER_CONNECTION_ID,
  B.LOCK_OWNER_TRANSACTION_ID,
  B.BLOCKED_TIME,
  B.WAITING_RECORD_ID,
  B.WAITING_SCHEMA_NAME,
  B.WAITING_TABLE_NAME,
  B.LOCK_TYPE,
  B.LOCK_MODE,
  C.CLIENT_HOST  AS LOCK_OWNER_HOST,
  C.CLIENT_PID   AS LOCK_OWNER_PID,
  C.USER_NAME    AS LOCK_OWNER_USER_NAME,
  C.LAST_ACTION  AS LOCK_OWNER_LAST_ACTION,
  P.STATEMENT_STRING AS BLOCKED_STATEMENT_STRING
FROM SYS.M_BLOCKED_TRANSACTIONS B
JOIN SYS.M_TRANSACTIONS T
  ON (B.HOST, B.PORT, B.LOCK_OWNER_TRANSACTION_ID) = (T.HOST, T.PORT, T.TRANSACTION_ID)
LEFT OUTER JOIN SYS.M_TRANSACTIONS TP
  ON (T.VOLUME_ID, T.PRIMARY_TRANSACTION_ID) = (TP.VOLUME_ID, TP.TRANSACTION_ID)
  AND TP.TRANSACTION_TYPE = 'USER TRANSACTION'
JOIN SYS.M_CONNECTIONS C
  ON MAP(TP.CONNECTION_ID, NULL, T.CONNECTION_ID, TP.CONNECTION_ID) = C.CONNECTION_ID
JOIN SYS.M_TRANSACTIONS TB
  ON (B.HOST, B.PORT, B.BLOCKED_TRANSACTION_ID) = (TB.HOST, TB.PORT, TB.TRANSACTION_ID)
LEFT OUTER JOIN SYS.M_TRANSACTIONS TBP
  ON (TB.VOLUME_ID, TB.PRIMARY_TRANSACTION_ID) = (TBP.VOLUME_ID, TBP.TRANSACTION_ID)
  AND TBP.TRANSACTION_TYPE = 'USER TRANSACTION'
JOIN SYS.M_CONNECTIONS CB
  ON MAP(TBP.CONNECTION_ID, NULL, TB.CONNECTION_ID, TBP.CONNECTION_ID) = CB.CONNECTION_ID
LEFT OUTER JOIN SYS.M_ACTIVE_STATEMENTS P
  ON CB.CURRENT_STATEMENT_ID = P.STATEMENT_ID
```

---

### Q18 – Count of Technical Tables Above Disk Threshold (≥1 GB)
**Function:** `fct_check_ttables` – query2.sql (wrapper)  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) FROM (<Q19 full query>)
```

---

### Q19 – Technical Tables Full Size Report
**Function:** `fct_check_ttables` – query1.sql  
**Connection key:** `STDMUSER<TENANT>`  
*Based on SAP Note 2388483 / HANA_Tables_LargestTables_2.00.040+*  
*Parameters: ONLY_TECHNICAL_TABLES = 'X', MIN_TABLE_DISK_SIZE_MB = 1024, ORDER_BY = TOTAL_DISK, RESULT_ROWS = 50*

```sql
WITH
BASIS_INFO AS
( SELECT
    '%'         SCHEMA_NAME,
    '%'         TABLE_NAME,
    '%'         STORE,
    ' '         ONLY_PAGED_TABLES,
    'X'         ONLY_TECHNICAL_TABLES,
    ' '         ONLY_TABLES_WITH_NSE_RECOMMENDATION,
    1024        MIN_TABLE_DISK_SIZE_MB,
    'TOTAL_DISK' ORDER_BY,
    50          RESULT_ROWS
  FROM DUMMY
),
TECHNICAL_TABLES AS
( SELECT
    CASE WHEN LOCATE(SCHEMA_TABLE_NAME, '.') = 0
         THEN '%'
         ELSE SUBSTR(SCHEMA_TABLE_NAME, 1, LOCATE(SCHEMA_TABLE_NAME, '.') - 1) END SCHEMA_NAME,
    CASE WHEN LOCATE(SCHEMA_TABLE_NAME, '.') = 0
         THEN SCHEMA_TABLE_NAME
         ELSE SUBSTR(SCHEMA_TABLE_NAME, LOCATE(SCHEMA_TABLE_NAME, '.') + 1) END TABLE_NAME
  FROM
  ( SELECT
      SUBSTR(B.TECHNICAL_TABLES, LOCATE(B.TECHNICAL_TABLES, ',', 1, O.ROWNO) + 1,
             LOCATE(B.TECHNICAL_TABLES, ',', 1, O.ROWNO + 1) - LOCATE(B.TECHNICAL_TABLES, ',', 1, O.ROWNO) - 1) SCHEMA_TABLE_NAME
    FROM
    ( SELECT TOP 1000 ROW_NUMBER() OVER () ROWNO FROM OBJECTS ) O,
    ( SELECT
        '%~~OLD,$BPC$HC$%,$BPC$TMP%,/1CPMB/%,/AIF/ALERT_IDX, ... [full list] ...,
         _SYS_STATISTICS.GLOBAL%,_SYS_STATISTICS.HOST%,_SYS_STATISTICS.TEL%,' TECHNICAL_TABLES
      FROM DUMMY
    ) B
  )
  WHERE SCHEMA_TABLE_NAME != ''
),
TABLES_HELPER AS
( SELECT T.SCHEMA_NAME, T.TABLE_NAME, T.HOST, T.STORE, T.RECORD_COUNT RECORDS,
         T.TABLE_MEM_MB, T.LOADED, T.HEAP_MEM_MB, T.PERS_MEM_MB, T.MAX_MEM_MB,
         T.PAGE_MEM_MB, IFNULL(CPS.PAGE_DISK_MB, 0) PAGE_DISK_MB, TP.TOTAL_DISK_MB,
         TC.NUM_COLUMNS, TC.PAGED_COLUMNS,
         IFNULL((SELECT MAX(MAP(LOAD_UNIT, 'PAGE', 1, 0)) FROM M_TABLE_PARTITIONS TP2
                 WHERE TP2.SCHEMA_NAME = T.SCHEMA_NAME AND TP2.TABLE_NAME = T.TABLE_NAME), 0) PAGED_PARTITIONS,
         -- ... index, LOB, partition counts via LEFT OUTER JOINs ...
         IFNULL(TT.TECHNICAL_TABLE, '') TECHNICAL_TABLE
  FROM BASIS_INFO BI
  INNER JOIN
  ( SELECT 'COLUMN' STORE, SCHEMA_NAME, TABLE_NAME,
           MAP(MIN(HOST), MAX(HOST), MIN(HOST), 'various') HOST,
           MAP(MAX(LOADED), 'NO', 'N', 'FULL', 'Y', 'PARTIALLY', 'P') LOADED,
           SUM(RECORD_COUNT) RECORD_COUNT,
           SUM(MEMORY_SIZE_IN_TOTAL + PERSISTENT_MEMORY_SIZE_IN_TOTAL) / 1024 / 1024 TABLE_MEM_MB,
           SUM(MEMORY_SIZE_IN_TOTAL) / 1024 / 1024 HEAP_MEM_MB,
           SUM(PERSISTENT_MEMORY_SIZE_IN_TOTAL) / 1024 / 1024 PERS_MEM_MB,
           SUM(ESTIMATED_MAX_MEMORY_SIZE_IN_TOTAL) / 1024 / 1024 MAX_MEM_MB,
           SUM(MEMORY_SIZE_IN_PAGE_LOADABLE_MAIN) / 1024 / 1024 PAGE_MEM_MB
    FROM M_CS_TABLES GROUP BY SCHEMA_NAME, TABLE_NAME HAVING SUM(RECORD_COUNT) >= 100
    UNION
    SELECT 'ROW' STORE, SCHEMA_NAME, TABLE_NAME,
           MAP(MIN(HOST), MAX(HOST), MIN(HOST), 'various') HOST, 'Y' LOADED,
           SUM(RECORD_COUNT) RECORD_COUNT,
           SUM(USED_FIXED_PART_SIZE + USED_VARIABLE_PART_SIZE) / 1024 / 1024 TABLE_MEM_MB,
           0 HEAP_MEM_MB, 0 PERS_MEM_MB, 0 MAX_MEM_MB, 0 PAGE_MEM_MB
    FROM M_RS_TABLES GROUP BY SCHEMA_NAME, TABLE_NAME
    HAVING SUM(USED_FIXED_PART_SIZE + USED_VARIABLE_PART_SIZE) >= 1024 * 1024
  ) T ON T.SCHEMA_NAME LIKE BI.SCHEMA_NAME AND T.TABLE_NAME LIKE BI.TABLE_NAME AND T.STORE LIKE BI.STORE
  -- ... further JOINs to M_TABLE_PERSISTENCE_STATISTICS, M_CS_COLUMNS_PERSISTENCE,
  --     M_CS_ALL_COLUMNS, M_RS_INDEXES, TABLE_COLUMNS, INDEXES, INDEX_COLUMNS,
  --     M_CS_PARTITIONS, M_TABLE_LOB_STATISTICS, TECHNICAL_TABLES ...
)
SELECT
  SCHEMA_NAME, TABLE_NAME,
  MAP(STORE, 'COLUMN', 'C', 'ROW', 'R') S,
  LOADED L,
  TECHNICAL_TABLE T,
  CASE WHEN UNIQUE_INDEXES = 0 THEN ' ' ELSE 'X' END U,
  MAP(PAGED, 0, ' ', 'X') P,
  LPAD(NUM_COLUMNS, 4) COLS,
  LPAD(RECORDS, 12) RECORDS,
  LPAD(TO_DECIMAL(TOTAL_DISK_MB / 1024, 10, 2), 7)  DISK_GB,
  LPAD(TO_DECIMAL(TOTAL_MEM_MB  / 1024, 10, 2), 7)  MEM_GB,
  LPAD(PARTITIONS, 5) PARTS,
  LPAD(TO_DECIMAL(TABLE_MEM_MB  / 1024, 10, 2), 10) TAB_MEM_GB,
  INDEXES,
  LPAD(TO_DECIMAL(INDEX_MEM_MB  / 1024, 10, 2), 10) IND_MEM_GB,
  LPAD(LOB_INFO, 4) LOBS,
  LPAD(TO_DECIMAL(LOB_DISK_MB   / 1024, 10, 2), 11) LOB_DISK_GB,
  LPAD(TO_DECIMAL(LOB_MEM_MB    / 1024, 10, 2), 10) LOB_MEM_GB,
  LPAD(TO_DECIMAL(SHARED_MEM_MB / 1024, 10, 2), 7)  SHAR_GB,
  LPAD(TO_DECIMAL(HEAP_MEM_MB   / 1024, 10, 2), 7)  HEAP_GB,
  LPAD(TO_DECIMAL(PERS_MEM_MB   / 1024, 10, 2), 7)  PERS_GB,
  LPAD(TO_DECIMAL(PAGE_MEM_MB   / 1024, 10, 2), 11) PAGE_MEM_GB,
  LPAD(TO_DECIMAL(PAGE_DISK_MB  / 1024, 10, 2), 12) PAGE_DISK_GB,
  LPAD(ROW_NUM, 3) POS,
  HOST,
  LPAD(TO_DECIMAL(MAX_TOTAL_MEM_MB / 1024, 10, 2), 10) MAX_MEM_GB,
  LPAD(TO_DECIMAL(SUM(TOTAL_MEM_MB)  OVER (ORDER BY ROW_NUM) / 1024, 5, 2), 7) MEM_CUM_GB,
  LPAD(TO_DECIMAL(SUM(TOTAL_DISK_MB) OVER (ORDER BY ROW_NUM) / 1024, 5, 2), 7) DISK_CUM_GB,
  LPAD(TO_DECIMAL(MEM_PCT, 5, 2), 7) MEM_PCT,
  LPAD(TO_DECIMAL(SUM(MEM_PCT) OVER (ORDER BY ROW_NUM), 5, 2), 7) CUM_PCT
FROM
( SELECT ...
  FROM BASIS_INFO BI, TABLES_HELPER T
  WHERE ( BI.ONLY_TECHNICAL_TABLES = ' ' OR T.TECHNICAL_TABLE = 'X' )
    AND ( BI.ONLY_TABLES_WITH_NSE_RECOMMENDATION = ' ' OR T.TABLE_NAME IN ('BALDAT','CDPOS','EDID4') )
    AND ( BI.ONLY_PAGED_TABLES = ' ' OR MAP(T.PAGED_COLUMNS, 0, T.PAGED_PARTITIONS, T.PAGED_COLUMNS) > 0 )
)
WHERE ( RESULT_ROWS = -1 OR ROW_NUM <= RESULT_ROWS )
ORDER BY ROW_NUM
WITH HINT (IGNORE_PLAN_CACHE)
```

---

### Q20 – Technical Tables Total Memory and Disk Used (GB)
**Function:** `fct_check_ttables` – query3.sql (wrapper)  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT
  TRIM(LAST_VALUE(MEM_CUM_GB  ORDER BY CUM_PCT)) AS MEM_USED_GB,
  TRIM(LAST_VALUE(DISK_CUM_GB ORDER BY CUM_PCT)) AS DISK_USED_GB
FROM (<Q19 full query>)
```

---

### Q21 – Count of Plan Cache Low Hit Ratio Events (<90%, last 40 days)
**Function:** `fct_check_memory` – sqlstmt  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) FROM (
  SELECT MAP(PLAN_CACHE_LOOKUP_COUNT, 0, 0,
             PLAN_CACHE_HIT_COUNT / PLAN_CACHE_LOOKUP_COUNT) AS PLAN_CACHE_HIT_RATIO
  FROM _SYS_STATISTICS.HOST_SQL_PLAN_CACHE_OVERVIEW
  WHERE SECONDS_BETWEEN(SNAPSHOT_ID, CURRENT_TIMESTAMP) <= 3456000
    AND MAP(PLAN_CACHE_LOOKUP_COUNT, 0, 0,
            PLAN_CACHE_HIT_COUNT / PLAN_CACHE_LOOKUP_COUNT) < 0.9
)
```

> **Note:** Threshold changed from 95% to 90% in v1.033 per SAP Note 2040002.

---

### Q22 – Plan Cache Low Hit Ratio Event Details (Top 50)
**Function:** `fct_check_memory` – sqlstmt1  
**Connection key:** `STDMUSER<TENANT>`  
*Runs only when Q21 returns > 0*

```sql
SELECT TOP 50
  SNAPSHOT_ID,
  PLAN_CACHE_LOOKUP_COUNT,
  PLAN_CACHE_HIT_COUNT,
  MAP(PLAN_CACHE_LOOKUP_COUNT, 0, 0,
      PLAN_CACHE_HIT_COUNT / PLAN_CACHE_LOOKUP_COUNT) AS PLAN_CACHE_HIT_RATIO
FROM _SYS_STATISTICS.HOST_SQL_PLAN_CACHE_OVERVIEW
WHERE SECONDS_BETWEEN(SNAPSHOT_ID, CURRENT_TIMESTAMP) <= 3456000
  AND MAP(PLAN_CACHE_LOOKUP_COUNT, 0, 0,
          PLAN_CACHE_HIT_COUNT / PLAN_CACHE_LOOKUP_COUNT) < 0.9
ORDER BY 4
```

---

### Q23 – Count of High Memory Allocators on Indexserver (>30% of total)
**Function:** `fct_check_memory` – sqlstmt2  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) FROM (
  SELECT TOP 10
    M_SERVICES.HOST,
    M_SERVICES.SERVICE_NAME,
    M_HEAP_MEMORY.CATEGORY,
    M_HEAP_MEMORY.INCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS INCLUSIVE_SIZE_IN_USE,
    M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS EXCLUSIVE_SIZE_IN_USE,
    ROUND(
      (M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024) /
      (SELECT TOP 1 ROUND((HEAP_MEMORY_ALLOCATED_SIZE + SHARED_MEMORY_USED_SIZE) / 1024 / 1024 / 1024, 2)
       FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY
       WHERE SERVICE_NAME = 'indexserver'
         AND HOST IN (SELECT HOST FROM M_SERVICES WHERE COORDINATOR_TYPE = 'MASTER' AND SERVICE_NAME = 'indexserver')
       ORDER BY SNAPSHOT_ID DESC) * 100, 2) AS PERCENT_FROM_TOTAL
  FROM M_HEAP_MEMORY, M_SERVICES
  WHERE M_HEAP_MEMORY.PORT  = M_SERVICES.PORT
    AND M_HEAP_MEMORY.HOST  = M_SERVICES.HOST
    AND M_SERVICES.SERVICE_NAME = 'indexserver'
  ORDER BY M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE DESC
)
WHERE PERCENT_FROM_TOTAL > 30
```

---

### Q24 – Top 10 Indexserver Memory Allocators (Detail)
**Function:** `fct_check_memory` – sqlstmt3  
**Connection key:** `STDMUSER<TENANT>`  
*Runs only when Q23 returns > 0*

```sql
SELECT TOP 10
  M_SERVICES.HOST,
  M_SERVICES.SERVICE_NAME,
  M_HEAP_MEMORY.CATEGORY,
  M_HEAP_MEMORY.INCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS INCLUSIVE_SIZE_IN_USE,
  M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024 AS EXCLUSIVE_SIZE_IN_USE,
  ROUND(
    (M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE / 1024 / 1024 / 1024) /
    (SELECT TOP 1 ROUND((HEAP_MEMORY_ALLOCATED_SIZE + SHARED_MEMORY_USED_SIZE) / 1024 / 1024 / 1024, 2)
     FROM _SYS_STATISTICS.HOST_SERVICE_MEMORY
     WHERE SERVICE_NAME = 'indexserver'
       AND HOST IN (SELECT HOST FROM M_SERVICES WHERE COORDINATOR_TYPE = 'MASTER' AND SERVICE_NAME = 'indexserver')
     ORDER BY SNAPSHOT_ID DESC) * 100, 2) AS PERCENT_FROM_TOTAL
FROM M_HEAP_MEMORY, M_SERVICES
WHERE M_HEAP_MEMORY.PORT  = M_SERVICES.PORT
  AND M_HEAP_MEMORY.HOST  = M_SERVICES.HOST
  AND M_SERVICES.SERVICE_NAME = 'indexserver'
ORDER BY M_HEAP_MEMORY.EXCLUSIVE_SIZE_IN_USE DESC
```

---

### Q25 – Count of OOM Trace Files on Tenant DB (last 40 days)
**Function:** `fct_check_memory` – sqlstmt4 (tenant run)  
**Connection key:** `STDMUSER<TENANT>`

```sql
SELECT COUNT(1) FROM (
  SELECT *
  FROM M_TRACEFILES
  WHERE SECONDS_BETWEEN(FILE_MTIME, CURRENT_TIMESTAMP) <= 3456000
    AND FILE_NAME LIKE '%oom%'
)
```

---

### Q26 – OOM Trace File Details on Tenant DB (Top 50)
**Function:** `fct_check_memory` – sqlstmt5 (tenant run)  
**Connection key:** `STDMUSER<TENANT>`  
*Runs only when Q25 returns > 0*

```sql
SELECT TOP 50 FILE_NAME, FILE_MTIME
FROM M_TRACEFILES
WHERE SECONDS_BETWEEN(FILE_MTIME, CURRENT_TIMESTAMP) <= 3456000
  AND FILE_NAME LIKE '%oom%'
ORDER BY FILE_MTIME DESC
```

---

## Queries Running on Both SYSTEMDB and Tenant DB

> The script first runs these against SYSTEMDB, then loops over each tenant database.

---

### Q27 – Count of P1 Alerts (last 40 days)
**Function:** `fct_check_alerts` – sqlstmt  
**Connection key:** `STDMUSER` (SYSTEMDB) + `STDMUSER<TENANT>` per tenant

```sql
SELECT COUNT(1) AS TOTAL_ALERTS_P1
FROM _SYS_STATISTICS.STATISTICS_ALERTS
WHERE SECONDS_BETWEEN(ALERT_TIMESTAMP, CURRENT_TIMESTAMP) <= 3456000
  AND ALERT_RATING = '1'
  AND ALERT_ID NOT IN ('17', '22', '23', '24')
```

---

### Q28 – P1 Alert Detail (Top 100)
**Function:** `fct_check_alerts` – sqlstmt2  
**Connection key:** `STDMUSER` (SYSTEMDB) + `STDMUSER<TENANT>` per tenant  
*Runs only when Q27 returns > 0*

```sql
SELECT TOP 100 *
FROM (
  SELECT
    COUNT(1)     AS NUM_OF_EVENTS,
    ALERT_RATING,
    ALERT_ID,
    INDEX,
    ALERT_DETAILS
  FROM _SYS_STATISTICS.STATISTICS_ALERTS
  WHERE SECONDS_BETWEEN(ALERT_TIMESTAMP, CURRENT_TIMESTAMP) <= 3456000
    AND ALERT_RATING = '1'
    AND ALERT_ID NOT IN ('17', '22', '23', '24')
  GROUP BY ALERT_RATING, ALERT_ID, INDEX, ALERT_DETAILS
  ORDER BY 1 DESC
)
```

---

### Q29 – Count of Column Store Tables with > 1.5 Billion Records
**Function:** `fct_check_bigtables` – sqlstmt  
**Connection key:** `STDMUSER` (SYSTEMDB) + `STDMUSER<TENANT>` per tenant

```sql
SELECT COUNT(1) AS BIG_TABLES
FROM M_CS_TABLES
WHERE RECORD_COUNT > '1500000000'
```

---

### Q30 – Big Tables Detail
**Function:** `fct_check_bigtables` – sqlstmt2  
**Connection key:** `STDMUSER` (SYSTEMDB) + `STDMUSER<TENANT>` per tenant  
*Runs only when Q29 returns > 0*

```sql
SELECT A.SCHEMA_NAME, A.TABLE_NAME, A.PART_ID, A.RECORD_COUNT
FROM M_CS_TABLES A
WHERE A.RECORD_COUNT > '1500000000'
ORDER BY 4 DESC
```

---

### Q31 – HDBuilderstore Connection Test
**Function:** `fct_check_hdbuserstore_connection` / `fct_check_hdbuserstore_w`  
**Connection key:** varies (called before every check)

```sql
SELECT * FROM DUMMY
```

---

## Execution Flow by Operation Mode

| `--operationCheck` | Checks Executed |
|---|---|
| `quickCheck` | CPU · Backups · Store Areas · Memory · Alerts · Blocked Transactions · Technical Tables · Big Tables |
| `quickCheckWParameters` | CPU · Backups · Store Areas · Memory · Alerts · Blocked Transactions · Technical Tables · Parameters · Big Tables |
| `getInfo` | CPU · Backups · Store Areas · Memory · Tenant list |
| `tTablesCheck` | Technical Tables only |

---

## Time Window and Thresholds

| Parameter | Value | Notes |
|---|---|---|
| `SECONDS_BETWEEN(...) <= 3456000` | **40 days** | Applied to all `_SYS_STATISTICS` history queries |
| CPU spike threshold | **≥ 95%** | Changed from 90% in v1.01 |
| Plan cache hit ratio | **< 0.90 (90%)** | Changed from 95% in v1.033 per SAP Note 2040002 |
| Memory allocator pressure | **> 30%** | Applied to both nameserver (SYSTEMDB) and indexserver (Tenant) |
| Big table threshold | **> 1,500,000,000 records** | Column store only |
| Technical table disk minimum | **1,024 MB** | Per table (query1.sql `MIN_TABLE_DISK_SIZE_MB`) |
