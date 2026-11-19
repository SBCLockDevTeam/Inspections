"""Assigned login IDs, account locks, resets, and legacy migration."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from alarm_inspection.storage import User, UserSession, open_store
from alarm_inspection.api.security import password_record, verify_password

ADMIN = 'john.porter@securitybuildingcontrols.com'
PASSWORD = 'TestBootstrapPassword42!'
TEMP = 'TemporaryPassword42!'


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "accounts.db"}')
    from alarm_inspection.api.app import create_app
    app = create_app()
    store = open_store()
    with store.begin() as session:
        session.query(User).one().force_password_reset = False
    client = TestClient(app)
    assert client.post('/api/auth/login', json={'email': ADMIN, 'password': PASSWORD}).status_code == 200
    assert client.patch('/api/admin/settings', json={'default_password': TEMP, 'force_password_reset_default': False}).status_code == 200
    return client, store


def create_user(client, username='Tech 42', email='tech@example.com'):
    response = client.post('/api/admin/users', json={'username': username, 'email': email})
    assert response.status_code == 200, response.text
    return response.json()['user']


def test_ids_required_email_and_rename(accounts):
    client, store = accounts
    for payload in ({'email': 'x@example.com'}, {'username': 'x'}, {'username': 'x', 'email': 'bad'}, {'username': '  ', 'email': 'x@example.com'}):
        assert client.post('/api/admin/users', json=payload).status_code == 400
    user = create_user(client)
    assert client.post('/api/admin/users', json={'username': ' tech 42 ', 'email': 'other@example.com'}).status_code == 409
    assert client.post('/api/admin/users', json={'username': 'other', 'email': 'TECH@example.com'}).status_code == 409
    tech = TestClient(client.app)
    assert tech.post('/api/auth/login', json={'username': 'tEcH 42', 'password': TEMP}).status_code == 200
    assert tech.get('/api/admin/users').status_code == 403
    assert tech.patch('/api/admin/users/'+user['id'], json={'reset_password': True}).status_code == 403
    assert client.patch('/api/admin/users/'+user['id'], json={'username': ADMIN}).status_code == 409
    assert client.patch('/api/admin/users/'+user['id'], json={'username': 'Installer-007'}).status_code == 200
    assert tech.post('/api/auth/login', json={'username': 'Tech 42', 'password': TEMP}).status_code == 401
    assert tech.post('/api/auth/login', json={'username': 'installer-007', 'password': TEMP}).status_code == 200
    with store() as session:
        saved = session.get(User, user['id'])
        assert saved.email == 'tech@example.com' and saved.username == 'Installer-007'
        assert verify_password(TEMP, saved.password_hash)


def test_lock_reset_and_self_protection(accounts):
    client, store = accounts
    user = create_user(client)
    path = '/api/admin/users/'+user['id']
    tech = TestClient(client.app)
    assert tech.post('/api/auth/login', json={'username': user['username'], 'password': TEMP}).status_code == 200
    assert client.patch(path, json={'is_active': False}).status_code == 200
    assert not tech.get('/api/auth/me').json()['authenticated']
    assert tech.post('/api/auth/login', json={'username': user['username'], 'password': TEMP}).status_code == 401
    assert client.patch(path, json={'is_active': True}).status_code == 200
    assert not tech.get('/api/auth/me').json()['authenticated']
    assert tech.post('/api/auth/login', json={'username': user['username'], 'password': TEMP}).status_code == 200
    assert tech.post('/api/auth/reset-password', json={'current_password': TEMP, 'new_password': 'MyOwnPassword42!'}).status_code == 200
    assert client.patch(path, json={'reset_password': True}).status_code == 200
    assert not tech.get('/api/auth/me').json()['authenticated']
    assert tech.post('/api/auth/login', json={'username': user['username'], 'password': 'MyOwnPassword42!'}).status_code == 401
    response = tech.post('/api/auth/login', json={'username': user['username'], 'password': TEMP})
    assert response.status_code == 200 and response.json()['user']['force_password_reset']
    assert tech.get('/api/inspections').status_code == 403
    admin = client.get('/api/auth/me').json()['user']
    for payload in ({'is_admin': False}, {'is_active': False, 'username': 'Should not change'}):
        assert client.patch('/api/admin/users/'+admin['id'], json=payload).status_code == 400
    with store() as session:
        saved = session.get(User, admin['id'])
        assert saved.is_admin and saved.is_active and saved.username == ADMIN


def test_legacy_login_migration_is_idempotent(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path / "legacy.db"}'
    monkeypatch.setenv('DATABASE_URL', url)
    engine = create_engine(url)
    original_hash = password_record(PASSWORD)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) UNIQUE, password_hash VARCHAR(600), is_admin BOOLEAN, force_password_reset BOOLEAN, is_active BOOLEAN, created_at DATETIME)'))
        conn.execute(text('INSERT INTO users VALUES (:id,:email,:password,1,0,1,:now)'), {'id': 'legacy', 'email': ADMIN, 'password': original_hash, 'now': datetime.now(timezone.utc)})
    store = open_store()
    with store.begin() as session:
        old = session.get(User, 'legacy')
        assert old.username == ADMIN and old.username_key == ADMIN
        assert old.password_hash == original_hash and old.is_active
        old.username = 'New ID'
        old.username_key = 'new id'
    with open_store()() as session:
        old = session.get(User, 'legacy')
        assert old.username == 'New ID' and old.email == ADMIN


def test_required_reset_without_old_password_revokes_other_sessions(accounts):
    client, store = accounts
    user = create_user(client)
    client.patch('/api/admin/users/'+user['id'], json={'reset_password': True})
    tech = TestClient(client.app)
    other = TestClient(client.app)
    for session in (tech, other):
        assert session.post('/api/auth/login', json={'username': user['username'], 'password': TEMP}).status_code == 200
    assert tech.post('/api/auth/reset-password', json={'new_password': 'short'}).status_code == 400
    response = tech.post('/api/auth/reset-password', json={'new_password': 'PersonalPassword42!'})
    assert response.status_code == 200
    assert response.json()['user']['username'] == 'Tech 42'
    assert not response.json()['user']['force_password_reset']
    assert tech.get('/api/auth/me').json()['authenticated']
    assert not other.get('/api/auth/me').json()['authenticated']
    assert TestClient(client.app).post('/api/auth/reset-password', json={'new_password': 'AttackPassword42!'}).status_code == 401
    assert other.post('/api/auth/login', json={'username': user['username'], 'password': TEMP}).status_code == 401
    assert other.post('/api/auth/login', json={'username': user['username'], 'password': 'PersonalPassword42!'}).status_code == 200
    # An ordinary password change still verifies the current password.
    assert other.post('/api/auth/reset-password', json={'new_password': 'AnotherPassword42!'}).status_code == 400


def test_admin_default_password_reset_survives_restart_without_bootstrap(accounts, monkeypatch):
    client, store = accounts
    client.patch('/api/admin/settings', json={'default_password': 'password'})
    admin = client.get('/api/auth/me').json()['user']
    assert client.patch('/api/admin/users/'+admin['id'], json={'reset_password': True}).status_code == 200
    monkeypatch.delenv('INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD', raising=False)
    from alarm_inspection.api.app import create_app
    restarted = TestClient(create_app())
    response = restarted.post('/api/auth/login', json={'username': admin['username'], 'password': 'password'})
    assert response.status_code == 200 and response.json()['user']['force_password_reset']
    assert restarted.post('/api/auth/reset-password', json={'new_password': 'RecoveredPassword42!'}).status_code == 200
