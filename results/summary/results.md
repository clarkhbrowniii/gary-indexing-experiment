# Measured indexing results

Python 3.13.2; SQLite 3.45.3; seed 6417; 7 measured runs and one warm-up per condition.

| Query | Rows | Baseline ms | Indexed ms | Change % | Index selected |
|---|---:|---:|---:|---:|---|
| source_identity | 1 | 6.742 | 0.023 | -99.66% | True |
| project_activity | 125 | 18.756 | 0.110 | -99.41% | True |
| employee_labor | 98 | 9.027 | 0.080 | -99.11% | True |
| project_labor | 3,000 | 129.651 | 230.008 | +77.41% | True |

## source_identity

Parameters: [1, "SYN-0125000"]

SQLite selected the candidate index. Median elapsed time decreased.

Baseline plan:
- SCAN SourceIdentity

Indexed plan:
- SEARCH SourceIdentity USING INDEX idx_source_identity_lookup (source_system_id=? AND source_key=?)

## project_activity

Parameters: [42, "2025-04-01 00:00:00", "2025-05-01 00:00:00"]

SQLite selected the candidate index. Median elapsed time decreased.

Baseline plan:
- SCAN ProductionActivity
- USE TEMP B-TREE FOR ORDER BY

Indexed plan:
- SEARCH ProductionActivity USING INDEX idx_production_project_time (project_id=? AND activity_timestamp>? AND activity_timestamp<?)

## employee_labor

Parameters: [42, "2025-04-01", "2025-06-30"]

SQLite selected the candidate index. Median elapsed time decreased.

Baseline plan:
- SCAN TimeEntry
- USE TEMP B-TREE FOR ORDER BY

Indexed plan:
- SEARCH TimeEntry USING INDEX idx_timeentry_person_date (person_id=? AND work_date>? AND work_date<?)

## project_labor

Parameters: ["2025-01-01", "2026-01-01"]

SQLite selected the candidate index. Median elapsed time increased; using an index does not guarantee faster execution. The reporting interval matches all time entries. This non-covering date index requires table-row access for project_id and hours and does not eliminate GROUP BY or ORDER BY temporary B-trees. These costs plausibly explain the observed slowdown; the plan does not expose the precise optimizer cost estimate.

Baseline plan:
- SCAN TimeEntry
- USE TEMP B-TREE FOR GROUP BY
- USE TEMP B-TREE FOR ORDER BY

Indexed plan:
- SEARCH TimeEntry USING INDEX idx_timeentry_work_date (work_date>? AND work_date<?)
- USE TEMP B-TREE FOR GROUP BY
- USE TEMP B-TREE FOR ORDER BY

All repeated and paired results passed multiset equality checks. Database integrity and foreign keys passed. All candidate indexes were removed.

Timings cover execution and full row materialization. Negative timing change means faster. Warmed caches and fixed baseline-first order limit causal timing claims; execution plans are primary evidence.
