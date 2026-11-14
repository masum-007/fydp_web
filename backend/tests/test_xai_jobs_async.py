"""Durable asynchronous XAI queue contract; no CNN weights or cloud services required."""
import hashlib
import io
import json
import time
from threading import Event
from uuid import uuid4

from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.database import connection, initialize
from app.main import create_app
from app.xai_jobs import XAIJobStore


class ReadyEngine:
    ready = True
    reason = None
    model_version = 'test-v3'

    def load(self):
        pass

    def predict_proba_from_face_crops(self, value):
        raise AssertionError('A synthetic test explanation must not run inference')


def image_png():
    out = io.BytesIO()
    Image.new('RGB', (32, 32), 'navy').save(out, 'PNG')
    return out.getvalue()


def setup_owned_analysis(client, settings, email='investigator@example.com'):
    password = 'Strong Password for XAI testing 2026'
    assert client.post('/api/auth/register', json={'name':'Investigator','email':email,'password':password}).status_code == 201
    login = client.post('/api/auth/login', json={'email':email,'password':password})
    assert login.status_code == 200
    token = {'Authorization':'Bearer '+login.json()['access_token']}
    owner_id = login.json()['user']['id']
    blob = image_png()
    upload = client.post('/api/evidence', headers=token,
                         files={'file':('synthetic.png',blob,'image/png')})
    assert upload.status_code == 201, upload.text
    eid = upload.json()['id']
    aid = str(uuid4())
    (settings.data_dir / 'analyses' / aid).mkdir(parents=True)
    result = {'analysis_id':aid,'evidence_id':eid,'prediction':'Fake',
              'fake_probability':.8,'threshold':.5,'model':'FourModelStacking',
              'model_version':'test-v3','image_sha256':hashlib.sha256(blob).hexdigest(),
              'xai':{},'assets':{}}
    with connection(settings) as db:
        db.execute('INSERT INTO analyses(id,user_id,evidence_id,result_json,created_at) VALUES(?,?,?,?,?)',
                   (aid,owner_id,eid,json.dumps(result),'2026-11-14T00:00:00+00:00'))
    return token,aid,owner_id


def test_persistent_queue_idempotence_restart_and_owner(tmp_path):
    settings = Settings(secret='s'*64, data_dir=tmp_path)
    initialize(settings)
    store = XAIJobStore(settings)
    store.install()
    # Setup database without a worker: show that a queued record is persistent.
    with connection(settings) as db:
        uid = str(uuid4()); eid=str(uuid4()); aid=str(uuid4())
        db.execute('INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)',
                   (uid,'User','u@test.com','test','2026-11-14T00:00:00+00:00'))
        db.execute("INSERT INTO evidence(id,user_id,filename,sha256,size_bytes,width,height,media_type,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (eid,uid,'x.png','a'*64,100,10,10,'image/png','2026-11-14T00:00:00+00:00'))
        db.execute('INSERT INTO analyses(id,user_id,evidence_id,result_json,created_at) VALUES(?,?,?,?,?)',
                   (aid,uid,eid,'{}','2026-11-14T00:00:00+00:00'))
    one=store.enqueue(uid,aid,'lime'); two=store.enqueue(uid,aid,'lime')
    assert one['id']==two['id'] and one['status']=='queued'
    assert XAIJobStore(settings).read(uid,aid,'lime')['status']=='queued'
    claimed=store.claim()
    assert claimed['id']==one['id']
    assert store.read(uid,aid,'lime')['status']=='running'
    store.interrupt_jobs_from_previous_process()
    assert store.read(uid,aid,'lime')['status']=='failed'
    retry=store.enqueue(uid,aid,'lime')
    assert retry['id']!=one['id'] and retry['status']=='queued'
    cancelled=store.cancel(uid,aid,'lime')
    assert cancelled['status']=='cancelled'
    assert store.read('another-user',aid,'lime') is None


def test_api_returns_immediately_and_polls_to_completed(tmp_path,monkeypatch):
    settings=Settings(secret='s'*64,data_dir=tmp_path,max_upload_bytes=100000)
    import app.main as main
    begun=Event(); done=Event()
    def generate(engine, source, method, *, landmarker_task, target_label):
        assert method=='lime' and target_label=='Fake' and source==image_png()
        begun.set()
        assert done.wait(8)
        return image_png(), {'status':'completed','method':method,'target_label':target_label,
                             'interpretation':{'status':'localized','narrative':'A test region',
                                               'regions':{'supporting':['mouth and chin']}}}
    monkeypatch.setattr(main,'generate_explanation',generate)
    with TestClient(create_app(settings,engine=ReadyEngine())) as client:
        user,aid,uid=setup_owned_analysis(client,settings)
        endpoint=f'/api/analyses/{aid}/explain/lime'
        before=time.monotonic()
        resp=client.post(endpoint,headers=user)
        assert resp.status_code==202,resp.text
        assert time.monotonic()-before<3
        first=resp.json()
        assert first['status'] in ('queued','running')
        assert client.post(endpoint,headers=user).json()['id']==first['id']
        assert begun.wait(3)
        status=client.get(endpoint+'/status',headers=user)
        assert status.status_code==200 and status.json()['status']=='running'
        assert 0<status.json()['progress']<100
        other,_,_=setup_owned_analysis(client,settings,'other@example.com')
        assert client.get(endpoint+'/status',headers=other).status_code==404
        assert client.post(endpoint,headers=other).status_code==404
        assert client.delete(f'/api/analyses/{aid}?confirm=true',headers=user).status_code==409
        assert client.delete(endpoint+'/job',headers=user).status_code==409
        done.set()
        for _ in range(40):
            if client.get(endpoint+'/status',headers=user).json()['status']=='completed': break
            time.sleep(.1)
        final=client.get(endpoint+'/status',headers=user)
        assert final.json()['status']=='completed',final.text
        result=client.get(f'/api/analyses/{aid}',headers=user).json()
        assert result['xai']['lime']['target_label']=='Fake'
        image=client.get(result['assets']['lime']['url'],headers=user)
        assert image.status_code==200 and image.content==image_png()
        assert client.get(result['assets']['lime']['url'],headers=other).status_code==404
        # Already saved: never rerun computation.
        assert client.post(endpoint,headers=user).json()['status']=='completed'


def test_failure_is_retryable_without_duplicate_processing(tmp_path,monkeypatch):
    settings=Settings(secret='s'*64,data_dir=tmp_path,max_upload_bytes=100000)
    import app.main as main
    calls={'count':0}
    def sometimes(engine,original,method,**kwargs):
        calls['count']+=1
        if calls['count']==1:
            raise RuntimeError('Synthetic XAI failure')
        return image_png(),{'status':'completed','target_label':'Fake',
                            'interpretation':{'regions':{'supporting':['nose']}}}
    monkeypatch.setattr(main,'generate_explanation',sometimes)
    with TestClient(create_app(settings,engine=ReadyEngine())) as client:
        user,aid,_=setup_owned_analysis(client,settings)
        endpoint=f'/api/analyses/{aid}/explain/shap'
        assert client.post(endpoint,headers=user).status_code==202
        for _ in range(80):
            status=client.get(endpoint+'/status',headers=user).json()['status']
            if status=='failed':break
            time.sleep(.05)
        assert status=='failed'
        assert client.post(endpoint,headers=user).status_code==202
        for _ in range(80):
            status=client.get(endpoint+'/status',headers=user).json()['status']
            if status=='completed':break
            time.sleep(.05)
        assert status=='completed' and calls['count']==2
