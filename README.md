# Gary indexing experiment

This repository tests the four logical indexing proposals supplied for Section 5.3 of the Gary Data Architecture Blueprint. It is an experiment, not a production implementation of Gary. Every record is synthetic; no real company or employee information is used.

The complete blueprint and Round 1 model were not supplied. The eight-table subset implements the entities, query columns, relationships, and reasonable integrity constraints specified in the request. Exact conformity to unspecified blueprint attributes is not claimed.

## Academic review

This [public repository](https://github.com/clarkhbrowniii/gary-indexing-experiment) provides the source code, SQL, measured execution plans, timing samples, and validation evidence for academic review. The generated databases are excluded from source control; reviewers can regenerate the fully synthetic dataset locally.

Start with [measured findings](results/summary/results.md), inspect [machine-readable evidence](results/summary/results.json), and consult [technical notes](docs/experiment-notes.md) and [clean-run reproduction checks](results/summary/reproducibility.json). The supplied query/index requirements are the basis of this experiment; the complete Gary blueprint is not included in this repository.

To review an independent run without overwriting the committed measurements:

~~~console
git clone https://github.com/clarkhbrowniii/gary-indexing-experiment.git
cd gary-indexing-experiment
python scripts/generate_data.py --db data/review.sqlite
python scripts/run_experiments.py --db data/review.sqlite --output data/review-results
~~~

Use a fresh database filename if repeating this review. Both the review database and its output remain under the ignored data directory. Compare logical results and execution plans with the committed evidence; elapsed times depend on the machine and SQLite version.

When referencing this work in an academic submission, include the repository URL, the commit SHA reviewed (from git rev-parse HEAD), and the Python/SQLite versions in the results. GitHub Issues are enabled for questions and reproducibility reports. Public visibility permits inspection; no license has been selected for this repository, so no additional reuse permissions are stated here.

## Requirements and reproduction

Python 3.10+ with its standard-library sqlite3 module; no pip dependencies. Git and GitHub CLI are needed only for source control and publishing.

From this repository root, on an empty data directory:

~~~powershell
python scripts/generate_data.py
python scripts/run_experiments.py
~~~

Generation refuses to overwrite an existing database. To repeat from a clean data state, explicitly remove the generated files and rerun:

~~~powershell
Remove-Item -LiteralPath data/gary.sqlite, data/gary.metadata.json
python scripts/generate_data.py
python scripts/run_experiments.py
~~~

The scripts resolve defaults relative to their own location, so they also work from another directory. Optional flags: generator --db and --seed; runner --db, --output, and --repeats (at least 3; default 7). A custom database requires its matching generated metadata sidecar. A different seed creates a different experiment. Hardware and timing vary; exact millisecond reproduction is not expected.

## Model and data

SourceSystem supplies SourceIdentity mappings to Person, Project, Application, or Endpoint. Endpoint references Person; ProductionActivity references Person, Project, Application, and Endpoint; TimeEntry references Person and Project. Integer primary keys, foreign keys, required fields, controlled vocabularies, and bounded durations/hours protect the subset. SourceIdentity uses triggers to validate polymorphic targets on insert/update. This narrow experiment does not implement a production lifecycle for deleting target entities.

Defaults: 15 systems, 3,000 people, 3,000 projects, 35 applications, 3,000 endpoints, 250,000 source identities, 800,000 activities, and 400,000 time entries. Fixed seed 6417, fixed calendar year 2025, transactions, and batches of 10,000 rows make generation repeatable and efficient. Work concentrates on active projects, more active people, popular applications, weekdays, and working hours; durations follow a skewed distribution. Individual home projects add correlated assignments. This is plausible synthetic load, not a calibrated model of any organization.

## Queries and indexes

| Experiment | Predicate | Candidate |
|---|---|---|
| Source identity resolution (point) | System and external key | UNIQUE SourceIdentity(source_system_id, source_key) |
| Project production activity (restricted range) | Project 42, April 2025 | ProductionActivity(project_id, activity_timestamp) |
| Employee labor history (restricted range) | Person 42, April through June 2025 inclusive | TimeEntry(person_id, work_date) |
| Project labor analysis (aggregation) | Entire year 2025 | TimeEntry(work_date) |

Actual identity parameters are taken from a fixed generated identity row. SQL lives in sql/02_queries.sql; indexes in sql/03_indexes.sql; cleanup in sql/04_cleanup.sql. Dates are fixed-width ISO text; the exact query boundaries distinguish inclusive BETWEEN from exclusive upper bounds.

## Method

Each comparison starts without secondary indexes, runs ANALYZE, captures EXPLAIN QUERY PLAN, warms the query once, then measures seven executions including fetchall with perf_counter_ns. The runner creates only the relevant candidate, runs ANALYZE again, and executes the same SQL and parameters on the same data. Separate connections for the two conditions avoid stale prepared plans. Automatic indexes are disabled and SQLite page cache is set to 64 MiB. Results are compared as multisets (including duplicates) because ORDER BY ties have no defined order. Raw timing samples, checksums, versions, parameters, and plans are saved in JSON. Medians, signed timing differences, plans, row counts, and observations also appear in CSV/Markdown and individual readable plan files.

Index inventory assertions verify isolation and final cleanup. Generation and measurement verify row counts, foreign keys, and database integrity. The runner checks rejection of invalid foreign keys, hours, null descriptions, duplicate identities, and missing polymorphic targets. No timing or conclusions are fabricated.

SQLite normally creates an automatic index for a UNIQUE(system,key) constraint. For a meaningful Query 1 baseline, the experiment instead enforces that uniqueness through triggers. Generation temporarily creates a unique loader index to accelerate trigger checks, then drops it before ANALYZE and every baseline. Initial schema creation has no explicit secondary indexes. Unrelated SQLite autoindexes for system names, project codes, application names, and endpoint tags remain and do not serve these four queries. A production schema with the composite UNIQUE constraint already has lookup support and should not add a redundant index.

## Actual results

Python 3.13.2; SQLite 3.45.3; seed 6417; 7 measured runs and one warm-up per condition.

| Query | Rows | Baseline ms | Indexed ms | Change % | Index selected |
|---|---:|---:|---:|---:|---|
| source_identity | 1 | 6.946 | 0.022 | -99.69% | true |
| project_activity | 125 | 19.274 | 0.213 | -98.90% | true |
| employee_labor | 98 | 9.666 | 0.086 | -99.11% | true |
| project_labor | 3,000 | 126.357 | 231.827 | +83.47% | true |

The table above reflects the latest machine-readable results in results/summary/results.json. Earlier measured runs remain available in Git history.

All four candidates were selected. The broad aggregation selected a non-covering date index even at 100% input selectivity and was slower. Its plan still uses temporary B-trees for grouping and ordering. This is an observed optimizer choice, not evidence that every analytical query should use a date index.

Full plans, raw measurements, parameters, and verification are in [results.md](results/summary/results.md), [results.json](results/summary/results.json), and [results.csv](results/summary/results.csv). The database is 62.79 MiB. Generation took 9.87 seconds on this machine.

Repository: [clarkhbrowniii/gary-indexing-experiment](https://github.com/clarkhbrowniii/gary-indexing-experiment) — public for academic review.

## Limits

Plans are primary evidence; timing is supporting evidence. Both conditions have an untimed warm-up, but OS caches are not flushed and baseline runs precede indexed runs. Index construction, statistics gathering, validation, and hashing are outside query timings. Python allocation and fetch costs are included. This tests one parameter set per query, no concurrent traffic, no write-throughput cost, and no alternative covering or composite designs. The broad labor interval intentionally includes all entries and may favor a scan. Results validate the indexing concepts within SQLite's optimizer and storage; they do not automatically generalize to Oracle, PostgreSQL, or any other engine.

The generated database and its metadata sidecar are ignored by Git. Source, SQL, documentation, and small measured result artifacts are tracked.

A second clean workflow reproduced identical query results/plans; see [reproducibility.json](results/summary/reproducibility.json).
