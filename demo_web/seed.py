from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from demo_web.db import connect, initialize, ROOT

EMAIL = 'qa.user@example.com'
PASSWORD = 'QaDemo!234'
WRONG_PASSWORD = 'WrongPass!234'
NAME = '테스트 사용자'
HASH_METHOD = 'scrypt:32768:8:1'


def seed(path):
    initialize(path)
    with connect(path) as db:
        # Never reset existing user data, including manual demo changes.
        if not db.execute('SELECT id FROM users WHERE email=?', (EMAIL,)).fetchone():
            db.execute('INSERT INTO users(email,password_hash,display_name,created_at) VALUES(?,?,?,?)',
                       (EMAIL, generate_password_hash(PASSWORD, method=HASH_METHOD), NAME,
                        datetime.now(timezone.utc).isoformat()))


if __name__ == '__main__':
    seed(ROOT / 'data/demo.db')
    print('데모 계정 준비 완료 (기존 데이터 보존)')
