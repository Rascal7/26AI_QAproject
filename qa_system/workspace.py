"""Workspace lists, ordered by execution time; date filters use Korea time."""

import json
from datetime import datetime, timezone, timedelta
from qa_system.storage import rows


def project_list(search='', tags=()):
    projects = rows("""SELECT p.*,
        (SELECT COUNT(*) FROM requirements r WHERE r.project_id=p.id) req_count,
        (SELECT COUNT(*) FROM test_cases t WHERE t.project_id=p.id) case_count,
        (SELECT MAX(started_at) FROM test_runs tr WHERE tr.project_id=p.id) last_run
        FROM projects p ORDER BY last_run DESC, p.id DESC""")
    return [
        p
        for p in projects
        if search.casefold() in (p['name'] + ' ' + p['target_url']).casefold()
        and (not tags or set(tags).intersection(json.loads(p['tags'])))
    ]


def all_tags():
    return sorted({t for p in rows('SELECT tags FROM projects') for t in json.loads(p['tags'])})


def run_date(value):
    dt = datetime.fromisoformat(value)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone(timedelta(hours=9))).date()


def run_list(tags=(), start=None, end=None):
    runs = rows("""SELECT tr.run_id,tr.project_id,tr.started_at,tr.finished_at,tr.status,tr.target_url,p.name,p.tags,
        (SELECT COUNT(*) FROM test_results r WHERE r.run_id=tr.run_id AND outcome='PASS') passed,
        (SELECT COUNT(*) FROM test_results r WHERE r.run_id=tr.run_id AND outcome='FAIL') failed,
        (SELECT COUNT(*) FROM test_results r WHERE r.run_id=tr.run_id AND outcome='ERROR') errors
        FROM test_runs tr JOIN projects p ON p.id=tr.project_id ORDER BY tr.started_at DESC,tr.rowid DESC""")
    return [
        r
        for r in runs
        if (not tags or set(tags).intersection(json.loads(r['tags'])))
        and (start is None or run_date(r['started_at']) >= start)
        and (end is None or run_date(r['started_at']) <= end)
    ]
