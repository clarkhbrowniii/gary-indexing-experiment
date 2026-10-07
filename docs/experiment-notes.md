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

Findings will be populated from the validated run.
