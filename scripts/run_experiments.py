"""Run four isolated baseline/index comparisons and verify actual results."""
import argparse
from collections import Counter
from contextlib import closing
import csv
import hashlib
import json
import platform
from pathlib import Path
import re
import sqlite3
from statistics import median
from time import perf_counter_ns

ROOT=Path(__file__).resolve().parents[1]
TYPES=['Point','Restricted range','Restricted range','Scan / aggregation']
INDEXES=['idx_source_identity_lookup','idx_production_project_time','idx_timeentry_person_date','idx_timeentry_work_date']

def sections(path):
    parts=re.split(r'^-- name: (\w+)\s*$',path.read_text(),flags=re.M)
    return {parts[i]:parts[i+1].strip() for i in range(1,len(parts),2)}

def secondary(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")]

def connect(db):
    conn=sqlite3.connect(db)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA automatic_index=OFF')
    conn.execute('PRAGMA cache_size=-65536')
    return conn

def measure(db,query,params,repeats):
    with closing(connect(db)) as conn:
        plan=[dict(id=r[0],parent=r[1],detail=r[3]) for r in conn.execute('EXPLAIN QUERY PLAN '+query,params)]
        conn.execute(query,params).fetchall()  # identical untimed warm-up per condition
        samples=[]
        reference=None
        for _ in range(repeats):
            start=perf_counter_ns()
            rows=conn.execute(query,params).fetchall()
            samples.append((perf_counter_ns()-start)/1e6)
            logical=Counter(rows)
            if reference is None:
                reference=logical
            assert logical==reference, 'Results changed between repetitions'
        digest=hashlib.sha256(json.dumps(sorted(reference.items()),separators=(',',':')).encode()).hexdigest()
        return dict(plan=plan,median_ms=median(samples),samples_ms=samples,row_count=len(rows),sha256=digest), reference

def validate_constraints(conn):
    cases=[("UPDATE TimeEntry SET hours=25 WHERE time_entry_id=1",()),
           ("UPDATE TimeEntry SET person_id=-1 WHERE time_entry_id=1",()),
           ("UPDATE TimeEntry SET description=NULL WHERE time_entry_id=1",()),
           ("INSERT INTO SourceIdentity SELECT 9999999,source_system_id,source_key,entity_type,entity_id FROM SourceIdentity WHERE source_identity_id=1",()),
           ("UPDATE SourceIdentity SET entity_id=9999999 WHERE source_identity_id=1",())]
    for sql,params in cases:
        conn.execute('SAVEPOINT validation')
        try:
            try:
                conn.execute(sql,params)
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('Constraint did not reject: '+sql)
        finally:
            conn.execute('ROLLBACK TO validation')
            conn.execute('RELEASE validation')
    return len(cases)

def run(db,out,repeats):
    if repeats<3:
        raise ValueError('At least three measured repetitions are required')
    if not db.is_file():
        raise FileNotFoundError(db)
    metadata=json.loads(db.with_suffix('.metadata.json').read_text())
    queries=sections(ROOT/'sql/02_queries.sql')
    indexes=sections(ROOT/'sql/03_indexes.sql')
    cleanup=(ROOT/'sql/04_cleanup.sql').read_text()
    for directory in ['baseline','indexed','summary']:
        (out/directory).mkdir(parents=True,exist_ok=True)
    conn=connect(db)
    results=[]
    try:
        unexpected=set(secondary(conn))-set(INDEXES)
        assert not unexpected, f'Unexpected secondary indexes: {unexpected}'
        conn.executescript(cleanup)
        counts={t:conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in metadata['counts']}
        assert counts==metadata['counts']
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        constraints=validate_constraints(conn)
        for position,(name,query) in enumerate(queries.items()):
            params=metadata['query_parameters'][name]
            index=INDEXES[position]
            conn.executescript(cleanup)
            assert secondary(conn)==[]
            conn.execute('ANALYZE')
            conn.commit()
            baseline,baseline_rows=measure(db,query,params,repeats)
            try:
                conn.execute(indexes[name])
                assert secondary(conn)==[index]
                conn.execute('ANALYZE')
                conn.commit()
                indexed,indexed_rows=measure(db,query,params,repeats)
                assert baseline_rows==indexed_rows, f'{name}: result mismatch'
                assert baseline['row_count']>0
                selected=any(index in p['detail'] for p in indexed['plan'])
                difference=(indexed['median_ms']/baseline['median_ms']-1)*100
                if selected:
                    interpretation='SQLite selected the candidate index. '+('Median elapsed time decreased.' if difference<0 else 'Median elapsed time increased; using an index does not guarantee faster execution.')
                    if name=='project_labor':
                        interpretation+=' The reporting interval matches all time entries. This non-covering date index requires table-row access for project_id and hours and does not eliminate GROUP BY or ORDER BY temporary B-trees. These costs plausibly explain the observed slowdown; the plan does not expose the precise optimizer cost estimate.'
                else:
                    interpretation='SQLite did not select the candidate index. '
                    interpretation+=('The reporting interval matches all time entries; a scan avoids indexed lookups for the entire table. GROUP BY and ORDER BY still require aggregation/sorting.' if name=='project_labor' else 'The observed plan is primary evidence; optimizer estimates can favor a scan.')
                result=dict(query_name=name,query_type=TYPES[position],parameters=params,candidate_index=index,
                            returned_row_count=baseline['row_count'],baseline=baseline,indexed=indexed,
                            timing_difference_percent=difference,index_selected=selected,results_identical=True,
                            interpretation=interpretation)
                if name=='project_labor':
                    result['matching_input_rows']=conn.execute('SELECT COUNT(*) FROM TimeEntry WHERE work_date>=? AND work_date<?',params).fetchone()[0]
                    result['input_selectivity_percent']=100*result['matching_input_rows']/counts['TimeEntry']
                results.append(result)
                for label,measurement in [('baseline',baseline),('indexed',indexed)]:
                    text=f'{name} / {label}\nParameters: {json.dumps(params)}\n'
                    text+='\n'.join(f"{p['id']} | parent {p['parent']} | {p['detail']}" for p in measurement['plan'])
                    text+=f"\nRows: {measurement['row_count']}\nMedian: {measurement['median_ms']:.6f} ms\n"
                    (out/label/(name+'.txt')).write_text(text)
                print(f"{name}: {baseline['median_ms']:.3f} -> {indexed['median_ms']:.3f} ms; rows={baseline['row_count']}; selected={selected}",flush=True)
            finally:
                conn.executescript(cleanup)
                assert secondary(conn)==[]
        conn.execute('ANALYZE')
        conn.commit()
        report=dict(platform=platform.platform(),machine=platform.machine(),python=platform.python_version(),sqlite=sqlite3.sqlite_version,seed=metadata['seed'],counts=counts,
                    generation=metadata,repeats=repeats,warmups_per_condition=1,cache_kib=65536,
                    automatic_index=False,timing_scope='Execute and fetch all rows; excludes equality validation and hashing',
                    comparison='Multiset equality, preserving duplicates; ORDER BY ties have no specified order',
                    percentage_convention='100 * (indexed / baseline - 1); negative means faster',
                    validation=dict(integrity_check='ok',foreign_key_violations=0,constraint_rejections=constraints,
                                    secondary_indexes_after_run=secondary(conn)),results=results)
        (out/'summary/results.json').write_text(json.dumps(report,indent=2)+'\n')
        fields=['query_name','query_type','parameters','returned_row_count','baseline_plan','indexed_plan',
                'baseline_median_ms','indexed_median_ms','timing_difference_percent','index_selected','results_identical','interpretation']
        with (out/'summary/results.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            writer.writeheader()
            for r in results:
                row={k:r[k] for k in fields if k in r}
                row.update(parameters=json.dumps(r['parameters']),baseline_plan=json.dumps(r['baseline']['plan']),
                           indexed_plan=json.dumps(r['indexed']['plan']),baseline_median_ms=r['baseline']['median_ms'],indexed_median_ms=r['indexed']['median_ms'])
                writer.writerow(row)
        lines=['# Measured indexing results','',f"Python {report['python']}; SQLite {report['sqlite']}; seed {report['seed']}; {repeats} measured runs and one warm-up per condition.",'',
               '| Query | Rows | Baseline ms | Indexed ms | Change % | Index selected |',
               '|---|---:|---:|---:|---:|---|']
        for r in results:
            lines.append(f"| {r['query_name']} | {r['returned_row_count']:,} | {r['baseline']['median_ms']:.3f} | {r['indexed']['median_ms']:.3f} | {r['timing_difference_percent']:+.2f}% | {r['index_selected']} |")
        for r in results:
            lines+=['',f"## {r['query_name']}",'',f"Parameters: {json.dumps(r['parameters'])}",'',r['interpretation'],'',
                    'Baseline plan:','\n'.join('- '+p['detail'] for p in r['baseline']['plan']),'',
                    'Indexed plan:','\n'.join('- '+p['detail'] for p in r['indexed']['plan'])]
        lines+=['','All repeated and paired results passed multiset equality checks. Database integrity and foreign keys passed. All candidate indexes were removed.',
                '', 'Timings cover execution and full row materialization. Negative timing change means faster. Warmed caches and fixed baseline-first order limit causal timing claims; execution plans are primary evidence.']
        (out/'summary/results.md').write_text('\n'.join(lines)+'\n')
    finally:
        conn.executescript(cleanup)
        conn.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'data/gary.sqlite')
    parser.add_argument('--output',type=Path,default=ROOT/'results')
    parser.add_argument('--repeats',type=int,default=7)
    args=parser.parse_args()
    run(args.db.resolve(),args.output.resolve(),args.repeats)
