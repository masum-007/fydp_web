import hashlib
import io
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


@pytest.fixture
def setup(tmp_path):
    settings = Settings(secret='test-only-' + 'x' * 48, data_dir=tmp_path, model_manifest=tmp_path / 'missing-manifest.json', max_upload_bytes=1024)
    with TestClient(create_app(settings)) as client:
        yield client, settings


def account(client, email='one@example.com'):
    body = {'name': 'Investigator', 'email': email, 'password': 'Strong test password 123!'}
    assert client.post('/api/auth/register', json=body).status_code == 201
    response = client.post('/api/auth/login', json={'email': email, 'password': body['password']})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def picture():
    output = io.BytesIO()
    Image.new('RGB', (12, 10), 'blue').save(output, format='PNG')
    return output.getvalue()


def test_authentication(setup):
    client, settings = setup
    assert client.get('/api/auth/me').status_code == 401
    headers = account(client)
    assert client.get('/api/auth/me', headers=headers).json()['email'] == 'one@example.com'
    assert client.post('/api/auth/login', json={'email': 'one@example.com', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/auth/register', json={'name': 'X', 'email': 'ONE@example.com', 'password': 'long password 123'}).status_code == 409
    assert client.post('/api/auth/register', json={'name': 'X', 'email': 'x@example.com', 'password': 'short'}).status_code == 422
    user_id = client.get('/api/auth/me', headers=headers).json()['id']
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode({'sub': user_id, 'iat': past, 'exp': past, 'iss': 'neuraledge', 'aud': 'neuraledge-api'}, settings.secret, algorithm='HS256')
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_evidence_integrity_and_owner_isolation(setup):
    client, settings = setup
    owner = account(client)
    data = picture()
    response = client.post('/api/evidence', headers=owner, files={'file': ('../../image.png', data, 'text/plain')})
    assert response.status_code == 201, response.text
    record = response.json()
    assert record['sha256'] == hashlib.sha256(data).hexdigest()
    assert record['filename'] == 'image.png'
    assert record['media_type'] == 'image/png'
    assert record['status'] == 'uploaded'
    assert 'prediction' not in record
    url = '/api/evidence/' + record['id']
    assert client.get(url + '/image', headers=owner).content == data
    stranger = account(client, 'two@example.com')
    assert client.get(url, headers=stranger).status_code == 404
    assert client.get(url + '/image', headers=stranger).status_code == 404
    assert client.get('/api/evidence', headers=stranger).json() == []
    assert len(client.get('/api/evidence', headers=owner).json()) == 1
    (settings.data_dir / 'uploads' / record['id']).write_bytes(b'tampered')
    assert client.get(url + '/image', headers=owner).status_code == 409


@pytest.mark.parametrize('data,code', [(b'', 422), (b'not an image', 422), (b'x' * 1025, 413)])
def test_invalid_uploads(setup, data, code):
    client, settings = setup
    headers = account(client)
    assert client.post('/api/evidence', headers=headers, files={'file': ('x.png', data, 'image/png')}).status_code == code
    assert client.get('/api/evidence', headers=headers).json() == []
    assert list((settings.data_dir / 'uploads').iterdir()) == []


def test_unsupported_format(setup):
    client, _ = setup
    output = io.BytesIO()
    Image.new('RGB', (2, 2)).save(output, format='GIF')
    assert client.post('/api/evidence', headers=account(client), files={'file': ('x.gif', output.getvalue())}).status_code == 415


def test_model_unavailable(setup):
    client, _ = setup
    assert client.get('/api/health').json()['inference_ready'] is False
    assert client.post('/api/analyze').status_code == 401
    headers = account(client)
    evidence = client.post('/api/evidence', headers=headers, files={'file': ('x.png', picture(), 'image/png')}).json()
    response = client.post('/api/analyze', headers=headers, json={'evidence_id': evidence['id']})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'MODEL_NOT_CONFIGURED'


def test_reject_placeholder_secret(tmp_path):
    with pytest.raises(ValueError):
        Settings(secret='REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', data_dir=tmp_path)


def test_analysis_persistence_assets_and_isolation(tmp_path):
    # Only a test double; production never substitutes mock predictions.
    class Engine:
        ready = True
        reason = None
        def load(self):
            pass
        def predict(self, data):
            return {'prediction': 'Fake', 'fake_probability': .8, 'threshold': .565}, {'heatmap': picture(), 'overlay': picture()}
    settings = Settings(secret='test-only-' + 'x' * 48, data_dir=tmp_path)
    app = create_app(settings, engine=Engine())
    with TestClient(app) as client:
        owner = account(client)
        evidence = client.post('/api/evidence', headers=owner, files={'file': ('image.png', picture())}).json()
        response = client.post('/api/analyze', headers=owner, json={'evidence_id': evidence['id']})
        assert response.status_code == 201, response.text
        result = response.json()
        analysis_id = result['analysis_id']
        assert client.get('/api/analyses/' + analysis_id, headers=owner).json() == result
        assert len(client.get('/api/analyses', headers=owner).json()) == 1
        assert client.get(result['assets']['overlay']['url'], headers=owner).content == picture()
        stranger = account(client, 'stranger@example.com')
        assert client.get('/api/analyses/' + analysis_id, headers=stranger).status_code == 404
        assert client.get(result['assets']['overlay']['url'], headers=stranger).status_code == 404
        assert client.post('/api/analyze', headers=stranger, json={'evidence_id': evidence['id']}).status_code == 404
        (tmp_path / 'analyses' / analysis_id / 'overlay.png').write_bytes(b'tampered')
        assert client.get(result['assets']['overlay']['url'], headers=owner).status_code == 409
