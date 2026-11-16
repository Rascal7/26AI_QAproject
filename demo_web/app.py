import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash
from demo_web.db import connect, ROOT
from demo_web.seed import seed

AUTH_MESSAGE = '이메일 또는 비밀번호가 올바르지 않습니다.'
UNAVAILABLE_MESSAGE = '현재 로그인할 수 없는 계정입니다.'
ERROR_MESSAGE = '요청을 처리하지 못했습니다. 다시 시도하세요.'
VARIANTS = ('normal', 'skip_disabled', 'skip_lock', 'skip_revalidation', 'misclassify_hash')


def hash_valid(value):
    # Only the seed's supported format is accepted; never pass arbitrary KDF cost to Werkzeug.
    return bool(re.fullmatch(r'scrypt:32768:8:1\$[A-Za-z0-9]{16}\$[0-9a-f]{128}', value))


def is_locked(user):
    return bool(user['locked_until'] and datetime.fromisoformat(user['locked_until']) > datetime.now(timezone.utc))


def create_app(db_path=None, *, testing=False, variant='normal'):
    if variant not in VARIANTS or (variant != 'normal' and not testing):
        raise ValueError('결함 모드는 테스트 실행에서만 허용됩니다.')
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32),
        DATABASE=str(db_path or ROOT / 'data/demo.db'),
        TESTING=testing,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('DEMO_HTTPS') == '1',
        MAX_CONTENT_LENGTH=8192,
    )

    def reject(status, code, message, **extra):
        session.clear()
        return jsonify(ok=False, error_code=code, message=message, **extra), status

    @app.get('/')
    def index():
        return redirect('/login')

    @app.get('/login')
    def login():
        return render_template('login.html')

    @app.post('/api/login')
    def authenticate():
        session.clear()
        body = request.get_json(silent=True)
        body = body if isinstance(body, dict) else {}
        email = body.get('email', '')
        password = body.get('password', '')
        email = email.strip().lower() if isinstance(email, str) else ''
        password = password if isinstance(password, str) else ''
        errors = {}
        if not email:
            errors['email'] = '이메일을 입력하세요.'
        elif not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            errors['email'] = '올바른 이메일 형식을 입력하세요.'
        if not password:
            errors['password'] = '비밀번호를 입력하세요.'
        if errors:
            return reject(400, 'VALIDATION_ERROR', '입력값을 확인하세요.', field_errors=errors)
        try:
            with connect(app.config['DATABASE']) as db:
                user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if user is None:
                return reject(401, 'INVALID_CREDENTIALS', AUTH_MESSAGE)
            if not hash_valid(user['password_hash']):
                if variant == 'misclassify_hash':
                    return reject(401, 'INVALID_CREDENTIALS', AUTH_MESSAGE)
                app.logger.warning('request_id=%s category=AUTH_DATA_ERROR', secrets.token_hex(8))
                return reject(503, 'AUTH_DATA_ERROR', ERROR_MESSAGE)
            if not check_password_hash(user['password_hash'], password):
                return reject(401, 'INVALID_CREDENTIALS', AUTH_MESSAGE)
            if (variant != 'skip_disabled' and user['status'] != 'active') or (
                variant != 'skip_lock' and is_locked(user)
            ):
                return reject(403, 'ACCOUNT_UNAVAILABLE', UNAVAILABLE_MESSAGE)
            session['user_id'] = user['id']
            return jsonify(ok=True, redirect_url='/home')
        except (sqlite3.Error, ValueError, TypeError):
            app.logger.warning('request_id=%s category=AUTH_DATA_ERROR', secrets.token_hex(8))
            return reject(503, 'AUTH_DATA_ERROR', ERROR_MESSAGE)

    @app.get('/home')
    def home():
        if not session.get('user_id'):
            return redirect('/login')
        try:
            with connect(app.config['DATABASE']) as db:
                user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
            if variant == 'skip_revalidation' and user is None:
                user = {'display_name': '테스트 사용자', 'email': 'qa.user@example.com'}
            elif (
                user is None
                or (variant != 'skip_disabled' and user['status'] != 'active')
                or (variant != 'skip_lock' and is_locked(user))
            ):
                session.clear()
                return redirect('/login')
        except (sqlite3.Error, ValueError, TypeError):
            session.clear()
            return redirect('/login')
        return render_template('home.html', user=user)

    return app


if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv(ROOT / '.env')
    seed(ROOT / 'data/demo.db')
    create_app().run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
