"""Generate deterministic synthetic AEC data; no third-party dependencies."""
import argparse
import json
import platform
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
COUNTS = dict(SourceSystem=15, Person=3000, Project=3000, Application=35,
              Endpoint=3000, SourceIdentity=250000, ProductionActivity=800000,
              TimeEntry=400000)
SEED = 6417

def batches(conn, sql, rows, size=10000):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            conn.executemany(sql, batch)
            batch.clear()
    if batch:
        conn.executemany(sql, batch)

def generate(db, seed):
    if db.exists():
        raise FileExistsError(f'{db} exists; choose a new path or remove it explicitly.')
    db.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    started = perf_counter()
    conn = sqlite3.connect(db)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.executescript((ROOT / 'sql/01_schema.sql').read_text())
        with conn:
            conn.executemany('INSERT INTO SourceSystem VALUES (?,?,?)',
                [(i, f'Synthetic system {i:02}', ['design','erp','collaboration','identity'][(i-1)%4]) for i in range(1,16)])
            conn.executemany('INSERT INTO Person VALUES (?,?,?,?)',
                [(i, f'Synthetic employee {i:04}', ['architecture','structural','civil','mep','management'][(i-1)%5], int(i%17!=0)) for i in range(1,3001)])
            conn.executemany('INSERT INTO Project VALUES (?,?,?,?)',
                [(i, f'AEC-{i:04}', f'Synthetic project {i:04}', 'active' if i<=600 else ('completed' if i%2 else 'planning')) for i in range(1,3001)])
            conn.executemany('INSERT INTO Application VALUES (?,?,?)',
                [(i, f'Synthetic application {i:02}', ['bim','cad','analysis','office'][(i-1)%4]) for i in range(1,36)])
            conn.executemany('INSERT INTO Endpoint VALUES (?,?,?,?)',
                [(i, f'SYN-{i:05}', i, 'laptop' if i%3==0 else 'workstation') for i in range(1,3001)])
            # Temporary loader index avoids quadratic trigger checks. It is removed
            # before ANALYZE and never exists in any baseline measurement.
            conn.execute('CREATE UNIQUE INDEX loader_identity_guard ON SourceIdentity(source_system_id,source_key)')
            def identities():
                for i in range(1,250001):
                    kind = rng.choices(['Person','Project','Application','Endpoint'], [40,30,5,25])[0]
                    maximum = 35 if kind=='Application' else 3000
                    system = rng.choices(range(1,16), weights=[35,20,10]+[3]*12)[0]
                    yield (i, system, f'SYN-{i:07}', kind, rng.randint(1,maximum))
            batches(conn, 'INSERT INTO SourceIdentity VALUES (?,?,?,?,?)', identities())
            conn.execute('DROP INDEX loader_identity_guard')
            dates = [(datetime(2025,1,1)+timedelta(days=i)).strftime('%Y-%m-%d') for i in range(365)]
            weekdays = [i for i in range(365) if (datetime(2025,1,1)+timedelta(days=i)).weekday()<5]
            def project(person):
                # 80% of work goes to 20% of projects; individuals have a home
                # project plus varied assignments. Includes known project 42.
                if rng.random()<0.45:
                    return (person-1)%600+1
                return rng.randint(1,600) if rng.random()<0.8 else rng.randint(601,3000)
            def day():
                return rng.choice(weekdays) if rng.random()<0.94 else rng.randrange(365)
            def activities():
                for i in range(1,800001):
                    person = rng.randint(1,600) if rng.random()<0.55 else rng.randint(601,3000)
                    yield (i, person, project(person), rng.choices(range(1,36), [15]*5+[1]*30)[0], person,
                           rng.choices(['model','draft','review','analyze'], [45,30,20,5])[0],
                           dates[day()]+f' {rng.randint(7,18):02}:{rng.randrange(60):02}:{rng.randrange(60):02}',
                           min(28800,max(1,int(rng.lognormvariate(5.8,1.0)))))
            batches(conn, 'INSERT INTO ProductionActivity VALUES (?,?,?,?,?,?,?,?)', activities())
            def entries():
                for i in range(1,400001):
                    person = rng.randint(1,600) if rng.random()<0.55 else rng.randint(601,3000)
                    yield (i, person, project(person), dates[day()], rng.choice([0.5,1,2,4,6,8]),
                           rng.choice(['Design coordination','Model development','Drawing review','Engineering analysis']))
            batches(conn, 'INSERT INTO TimeEntry VALUES (?,?,?,?,?,?)', entries())
        conn.execute('ANALYZE')
        conn.commit()
        observed = {name:conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in COUNTS}
        assert observed == COUNTS, observed
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall()
        identity = conn.execute('SELECT source_system_id,source_key FROM SourceIdentity WHERE source_identity_id=125000').fetchone()
        metadata = dict(seed=seed, counts=observed, python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                        generation_seconds=perf_counter()-started, database_bytes=db.stat().st_size,
                        query_parameters=dict(source_identity=list(identity), project_activity=[42,'2025-04-01 00:00:00','2025-05-01 00:00:00'],
                        employee_labor=[42,'2025-04-01','2025-06-30'], project_labor=['2025-01-01','2026-01-01']))
        db.with_suffix('.metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(json.dumps(metadata,indent=2))
    finally:
        conn.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'data/gary.sqlite')
    parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args()
    generate(args.db.resolve(), args.seed)
