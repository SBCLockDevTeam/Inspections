"""HTTPS session cookies do not travel over HTTP or survive logout."""
import pytest
from fastapi.testclient import TestClient
from alarm_inspection.api.security import SESSION_COOKIE


@pytest.mark.parametrize('secure', [False, True])
def test_session_cookie_transport(tmp_path, monkeypatch, secure):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "cookie.db"}')
    monkeypatch.setenv('INSPECTIONS_COOKIE_SECURE', str(secure).lower())
    from alarm_inspection.api.app import create_app
    with TestClient(create_app(), base_url='https://inspections.example.test') as client:
        response = client.post('/api/auth/login', json={
            'email': 'john.porter@securitybuildingcontrols.com',
            'password': 'TestBootstrapPassword42!',
        })
        assert response.status_code == 200
        cookie = response.headers['set-cookie']
        assert ('; Secure' in cookie) is secure
        assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
        assert client.get('/api/auth/me').json()['authenticated']
        assert client.get('http://inspections.example.test/api/auth/me').json()['authenticated'] is (not secure)
        assert client.post('/api/auth/logout').status_code == 200
        assert not client.get('/api/auth/me').json()['authenticated']
        assert SESSION_COOKIE not in client.cookies
