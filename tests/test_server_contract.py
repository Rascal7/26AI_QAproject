from datetime import datetime, timedelta, timezone
import pytest
from demo_web.app import create_app
from demo_web.db import connect
from demo_web.seed import EMAIL, PASSWORD, seed


@pytest.fixture
def server_client(tmp_path):
    path = tmp_path / 'server.sqlite3'
    seed(path)
    app = create_app(path, testing=True)
    return app.test_client(), path


def test_server_validation_and_normalization(server_client):
    client, _ = server_client
    for payload in ({}, [], {'email': 1, 'password': []}, {'email': '', 'password': ''}):
        response = client.post('/api/login', json=payload)
        assert response.status_code == 400
        assert set(response.json['field_errors']) == {'email', 'password'}
    assert client.post('/api/login', json={'email': 'invalid', 'password': PASSWORD}).status_code == 400
    assert client.post('/api/login', json={'email': EMAIL, 'password': PASSWORD + ' '}).status_code == 401
    response = client.post('/api/login', json={'email': '  QA.USER@EXAMPLE.COM  ', 'password': PASSWORD})
    assert response.status_code == 200
    cookie = response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Secure' not in cookie
    with client.session_transaction() as session:
        assert set(session) == {'user_id'}


def test_wrong_password_precedes_disabled_check(server_client):
    client, path = server_client
    with connect(path) as db:
        db.execute("UPDATE users SET status='disabled'")
    response = client.post('/api/login', json={'email': EMAIL, 'password': 'incorrect'})
    assert response.status_code == 401
    assert response.json['error_code'] == 'INVALID_CREDENTIALS'


@pytest.mark.parametrize('change', ['disabled', 'locked', 'deleted'])
def test_home_revalidates_current_state(server_client, change):
    client, path = server_client
    assert client.post('/api/login', json={'email': EMAIL, 'password': PASSWORD}).status_code == 200
    with connect(path) as db:
        if change == 'disabled':
            db.execute("UPDATE users SET status='disabled'")
        elif change == 'locked':
            db.execute(
                'UPDATE users SET locked_until=?', ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),)
            )
        else:
            db.execute('DELETE FROM users')
    assert client.get('/home').status_code == 302
    with client.session_transaction() as session:
        assert 'user_id' not in session


def test_expired_lock_and_failed_relogin_clear_session(server_client):
    client, path = server_client
    with connect(path) as db:
        db.execute(
            'UPDATE users SET locked_until=?', ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),)
        )
    assert client.post('/api/login', json={'email': EMAIL, 'password': PASSWORD}).status_code == 200
    assert client.post('/api/login', json={'email': EMAIL, 'password': 'incorrect'}).status_code == 401
    with client.session_transaction() as session:
        assert not session


def test_fault_variants_are_not_public():
    with pytest.raises(ValueError):
        create_app(variant='skip_disabled')
