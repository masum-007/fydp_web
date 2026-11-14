"""Authenticated profile/security and active-manifest analytics regressions."""
import json
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

class Stub:
    ready=True
    reason=None
    models={name:object() for name in ("MobileNetV2","ResNet50V2","Xception","EfficientNetB0")}
    threshold=.5
    model_version="unit-test-v3"
    def load(self):pass


def client_for(tmp_path, manifest=None):
    settings=Settings(secret='t'*64,data_dir=tmp_path/'storage',model_manifest=manifest or tmp_path/'missing.json')
    return TestClient(create_app(settings,engine=Stub()))


def register_login(client, email='first@example.com'):
    password='not a production password 1234'
    r=client.post('/api/auth/register',json={'name':'Demo Investigator','email':email,'password':password})
    assert r.status_code==201,r.text
    r=client.post('/api/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']},password


def test_profile_session_listing_and_revocation(tmp_path):
    with client_for(tmp_path) as client:
        h,pw=register_login(client)
        a=client.patch('/api/auth/profile',headers=h,json={'name':'New Investigator'})
        assert a.status_code==200,a.text
        assert a.json()['name']=='New Investigator'
        assert client.post('/api/auth/refresh').json()['user']['name']=='New Investigator'
        assert client.patch('/api/auth/profile',headers=h,json={'name':'  '}).status_code==422
        second=client.post('/api/auth/login',json={'email':'first@example.com','password':pw})
        assert second.status_code==200
        second_h={'Authorization':'Bearer '+second.json()['access_token']}
        assert len(client.get('/api/auth/sessions',headers=second_h).json())==2
        assert len([s for s in client.get('/api/auth/sessions',headers=second_h).json() if s['is_current']])==1
        assert client.post('/api/auth/sessions/revoke-others',headers=second_h).json()['revoked']==1
        assert client.get('/api/auth/me',headers=h).status_code==401
        assert client.get('/api/auth/me',headers=second_h).status_code==200
        assert client.post('/api/auth/sessions/revoke-all',headers=second_h).status_code==204
        assert client.get('/api/auth/me',headers=second_h).status_code==401
        assert client.post('/api/auth/refresh').status_code==401


def test_password_change_revokes_all_and_checks_current(tmp_path):
    with client_for(tmp_path) as client:
        h,password=register_login(client)
        assert client.post('/api/auth/password',headers=h,json={'current_password':'wrong','new_password':'another secure password 2026'}).status_code==400
        assert client.post('/api/auth/password',headers=h,json={'current_password':password,'new_password':'tiny'}).status_code==422
        r=client.post('/api/auth/password',headers=h,json={'current_password':password,'new_password':'another secure password 2026'})
        assert r.status_code==204,r.text
        assert client.get('/api/auth/me',headers=h).status_code==401
        assert client.post('/api/auth/refresh').status_code==401
        assert client.post('/api/auth/login',json={'email':'first@example.com','password':password}).status_code==401
        assert client.post('/api/auth/login',json={'email':'first@example.com','password':'another secure password 2026'}).status_code==200


def test_profile_and_research_require_token_and_are_account_scoped(tmp_path):
    manifest=tmp_path/'deployment.json'
    manifest.write_text(json.dumps({'model_order':['MobileNetV2','ResNet50V2','Xception','EfficientNetB0'],
      'operating_threshold':.5,
      'test_set_metrics':[{'model':'Stacking_TTA','threshold':.5,'n':155,'accuracy':.916129,
                           'fake_F1':.915,'ROC_AUC':.9745,'TN':72,'FP':7,'FN':6,'TP':70},
                          {'model':'Stacking_TTA','threshold':.65,'accuracy':.99},
                          {'model':'OldVersion','threshold':.5,'accuracy':1.0}],
      'research_caveats':['Test split not independent.']}))
    with client_for(tmp_path,manifest) as client:
        assert client.patch('/api/auth/profile',json={'name':'Other'}).status_code==401
        assert client.get('/api/model-research').status_code==401
        first,_=register_login(client)
        rows=client.get('/api/model-research',headers=first)
        assert rows.status_code==200
        data=rows.json()
        assert data['available'] is True and len(data['metrics'])==1
        assert data['metrics'][0]['n']==155
        assert data['metrics'][0]['threshold']==.5
        assert 'OldVersion' not in str(data)
        second,_=register_login(client,'second@example.com')
        assert client.patch('/api/auth/profile',headers=second,json={'name':'Second'}).status_code==200
        assert client.get('/api/auth/me',headers=first).json()['name']=='Demo Investigator'


def test_eight_character_passwords_registration_and_change(tmp_path):
    """Both registration and password change accept eight, but reject seven characters."""
    with client_for(tmp_path) as client:
        email = 'eight-chars@example.com'
        register = '/api/auth/register'
        login = '/api/auth/login'
        change = '/api/auth/password'
        assert client.post(register, json={
            'name': 'Eight Char Tester', 'email': email, 'password': 'Abcd123',
        }).status_code == 422
        assert client.post(register, json={
            'name': 'Eight Char Tester', 'email': email, 'password': 'Abcd1234',
        }).status_code == 201
        result = client.post(login, json={'email': email, 'password': 'Abcd1234'})
        assert result.status_code == 200
        headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
        assert client.post(change, headers=headers, json={
            'current_password': 'Abcd1234', 'new_password': 'New1234',
        }).status_code == 422
        assert client.post(change, headers=headers, json={
            'current_password': 'Abcd1234', 'new_password': 'New12345',
        }).status_code == 204
        assert client.post(login, json={'email': email, 'password': 'Abcd1234'}).status_code == 401
        assert client.post(login, json={'email': email, 'password': 'New12345'}).status_code == 200
