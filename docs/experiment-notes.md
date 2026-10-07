# Technical experiment notes

## Scope and integrity assumptions

The experiment follows the supplied Section 5.3 query/index specifications, not an independently available complete blueprint. Text date constraints enforce shape, not every valid calendar date. Synthetic dates come from Python datetime. SourceIdentity entity references are polymorphic, so insert/update triggers validate target existence; a production lifecycle would need stronger deletion rules. Person/project assignments and endpoint ownership are correlated during generation, but no additional business rule is inferred from the missing Round 1 specification.

## Baseline isolation

SourceIdentity's natural key is enforced by insert/update triggers to avoid an automatic composite UNIQUE index in the baseline. A temporary loader index speeds the duplicate check across 250,000 inserts. That index is removed within the generation transaction before any query measurement. Explicit index inventory checks prohibit leftover loader or unrelated secondary indexes. Table primary keys use INTEGER PRIMARY KEY rowid aliases. Other UNIQUE columns produce unavoidable SQLite autoindexes that cannot satisfy the experimental predicates.

ANALYZE runs after loading, before each baseline, after candidate creation, and after cleanup. Statements are prepared in fresh measurement connections after the schema/statistics change. Only one candidate is present at a time. A final cleanup also runs in a finally block if a query measurement fails.

## Timing and equality

perf_counter_ns is monotonic and high resolution. Each condition performs one warm-up followed by seven complete execute/fetchall calls. Result checking and SHA-256 construction happen outside the timer. Multiset equality preserves duplicate rows and permits arbitrary order among tied timestamps, dates, or aggregate totals. Hours are multiples of 0.5, exactly representable in binary, so aggregate sums do not introduce floating-order differences here.

The process fixes SQLite cache capacity but cannot reset operating-system caches. Fixed baseline-first ordering, index construction warming filesystem pages, and Python materialization can influence timings. Measurements are warm-query observations on this machine, not cold storage or causal universal speedup estimates. No forced INDEXED BY or NOT INDEXED clauses are used; index selection is the optimizer's actual choice. Automatic indexes are disabled equally in both conditions to preserve isolation.

## Observed findings

### source_identity

SQLite selected the candidate index. Median elapsed time decreased.

Baseline: SCAN SourceIdentity. Indexed: SEARCH SourceIdentity USING INDEX idx_source_identity_lookup (source_system_id=? AND source_key=?).

Measured median: 6.742 → 0.023 ms (-99.66%). Returned rows: 1.

### project_activity

SQLite selected the candidate index. Median elapsed time decreased.

Baseline: SCAN ProductionActivity; USE TEMP B-TREE FOR ORDER BY. Indexed: SEARCH ProductionActivity USING INDEX idx_production_project_time (project_id=? AND activity_timestamp>? AND activity_timestamp<?).

Measured median: 18.756 → 0.110 ms (-99.41%). Returned rows: 125.

### employee_labor

SQLite selected the candidate index. Median elapsed time decreased.

Baseline: SCAN TimeEntry; USE TEMP B-TREE FOR ORDER BY. Indexed: SEARCH TimeEntry USING INDEX idx_timeentry_person_date (person_id=? AND work_date>? AND work_date<?).

Measured median: 9.027 → 0.080 ms (-99.11%). Returned rows: 98.

### project_labor

SQLite selected the candidate index. Median elapsed time increased; using an index does not guarantee faster execution. The reporting interval matches all time entries. This non-covering date index requires table-row access for project_id and hours and does not eliminate GROUP BY or ORDER BY temporary B-trees. These costs plausibly explain the observed slowdown; the plan does not expose the precise optimizer cost estimate.

Baseline: SCAN TimeEntry; USE TEMP B-TREE FOR GROUP BY; USE TEMP B-TREE FOR ORDER BY. Indexed: SEARCH TimeEntry USING INDEX idx_timeentry_work_date (work_date>? AND work_date<?); USE TEMP B-TREE FOR GROUP BY; USE TEMP B-TREE FOR ORDER BY.

Measured median: 129.651 → 230.008 ms (77.41%). Returned rows: 3000.

The broad query returns 3,000 aggregate groups from 400,000 matching input entries (100% of TimeEntry). EXPLAIN QUERY PLAN shows a SEARCH using idx_timeentry_work_date, plus temporary B-trees for GROUP BY and ORDER BY. Selecting the available index despite its measured slowdown is the unexpected finding; timing cannot reveal the exact optimizer cost estimate. The three selective queries change from SCAN to SEARCH and the two ordered range queries eliminate their sort temporary B-tree.

Validation: clean-state generation, expected counts, integrity_check=ok, zero foreign-key violations, five invalid-write rejections, nonempty queries, seven repeat-equality checks per condition, paired multiset equality, plan capture, and index isolation/cleanup all passed. Python 3.13.2; SQLite 3.45.3.


A second complete clean workflow reproduced identical counts, query parameters, logical result hashes, and execution plans. Timings varied, with the same direction of effect in every comparison. Evidence is recorded in results/summary/reproducibility.json.

All eight tables also passed full-content SHA-256 comparison between clean generations. Hash input is each row in primary-key order, serialized with Python json.dumps(row, separators=(",", ":")), followed by a newline, encoded as UTF-8. Physical SQLite file hashes differ after different numbers of schema/statistics cycles; logical data reproducibility is the relevant check.
