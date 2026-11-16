"""Only this capability object may mutate a registered disposable test database."""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from demo_web.db import connect
from demo_web.seed import EMAIL, seed
from demo_web.app import hash_valid


class ScenarioDB:
    def __init__(self, path, root):
        self.path, self.root = Path(path).resolve(), Path(root).resolve()
        if self.path.parent != self.root or self.path.name != 'test.sqlite3':
            raise ValueError('테스트 전용 DB 경로가 아닙니다.')
        if self.path.exists():
            raise ValueError('기존 DB를 초기화하지 않습니다.')
        seed(self.path)
        assert self.snapshot()['count'] == 1

    def _check(self):
        if self.path.resolve().parent != self.root or not self.path.is_file():
            raise ValueError('테스트 DB 경로가 변경되었습니다.')

    def snapshot(self):
        self._check()
        with connect(self.path) as db:
            rows = db.execute('SELECT * FROM users').fetchall()
            return {
                'count': len(rows),
                'users': [
                    dict(
                        id=r['id'],
                        email=r['email'],
                        display_name=r['display_name'],
                        status=r['status'],
                        locked_until=r['locked_until'],
                        hash_format_valid=hash_valid(r['password_hash']),
                    )
                    for r in rows
                ],
            }

    def prepare(self, scenario):
        self._check()
        with connect(self.path) as db:
            if scenario == 'DB-001':
                db.execute('UPDATE users SET status=? WHERE email=?', ('disabled', EMAIL))
            elif scenario == 'DB-002':
                self.locked_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                db.execute('UPDATE users SET locked_until=? WHERE email=?', (self.locked_until, EMAIL))
            elif scenario == 'DB-003':
                db.execute('UPDATE users SET password_hash=? WHERE email=?', ('invalid-hash-format', EMAIL))
            elif scenario not in (None, 'DB-004', 'DB-005'):
                raise ValueError('등록되지 않은 시나리오')
        snap = self.snapshot()
        assert snap['count'] == 1
        user = snap['users'][0]
        if scenario == 'DB-001':
            assert user['status'] == 'disabled'
        if scenario == 'DB-002':
            assert user['status'] == 'active' and user['locked_until'] == self.locked_until
            assert datetime.fromisoformat(user['locked_until']) > datetime.now(timezone.utc)
        if scenario == 'DB-003':
            assert user['hash_format_valid'] is False
        return snap

    def delete_user(self):
        self._check()
        with connect(self.path) as db:
            db.execute('DELETE FROM users WHERE email=?', (EMAIL,))
        assert self.snapshot()['count'] == 0

    def reject_duplicate(self):
        self._check()
        with connect(self.path) as db:
            original = tuple(db.execute('SELECT * FROM users WHERE email=?', (EMAIL,)).fetchone())
            rejected = False
            try:
                db.execute(
                    'INSERT INTO users(email,password_hash,display_name,created_at) VALUES(?,?,?,?)',
                    (EMAIL, 'unused', '다른 사용자', datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError:
                rejected = True
                db.rollback()
            assert rejected, 'UNIQUE 제약이 중복 이메일을 거부해야 합니다.'
        with connect(self.path) as db:
            rows = db.execute('SELECT * FROM users WHERE email=?', (EMAIL,)).fetchall()
            assert len(rows) == 1
            assert tuple(rows[0]) == original, '기존 데이터가 변경되었습니다.'
        return True
