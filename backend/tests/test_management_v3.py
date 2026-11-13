"""Regression tests for case editing, unlinking, deletion, and report associations.
Run with: python -m pytest tests/test_management_v3.py -q
"""
import io
import json
from uuid import uuid4
from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.database import connection
from app.main import create_app


class DummyEngine:
    ready = True
    reason = None
    threshold = 0.65
    model_version = "test-model-v2"
    models = {name: object() for name in ("MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0")}
    def load(self):
        return None


def register(client, email):
    response = client.post("/api/auth/register", json={
        "name": "Investigator", "email": email, "password": "correct horse battery 123"
    })
    assert response.status_code == 201, response.text
    response = client.post("/api/auth/login", json={
        "email": email, "password": "correct horse battery 123"
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}, response.json()["user"]["id"]


def png():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, format="PNG")
    return buf.getvalue()


def seed_analysis(client, settings, headers, user_id):
    evidence = client.post("/api/evidence", headers=headers,
                           files={"file": ("test.png", png(), "image/png")})
    assert evidence.status_code == 201, evidence.text
    eid = evidence.json()["id"]
    aid = str(uuid4())
    directory = settings.data_dir / "analyses" / aid
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "overlay.png").write_bytes(png())
    with connection(settings) as db:
        db.execute("INSERT INTO analyses VALUES (?,?,?,?,?)", (
            aid, user_id, eid, json.dumps({"analysis_id": aid, "evidence_id": eid,
            "model": "FourModelStacking", "prediction": "Fake", "confidence": 0.9,
            "created_at": "2026-11-12T12:00:00+00:00"}), "2026-11-12T12:00:00+00:00"))
    return aid, eid, directory


def test_case_edit_unlink_delete_and_shared_analysis(tmp_path):
    settings = Settings(secret="test-only-" + "x"*48, data_dir=tmp_path,
                        model_manifest=tmp_path / "missing.json", max_upload_bytes=512000)
    with TestClient(create_app(settings, engine=DummyEngine())) as client:
        a, owner_id = register(client, "owner@example.com")
        b, _ = register(client, "other@example.com")
        assert client.get("/api/model-info").status_code == 401
        model_info = client.get("/api/model-info", headers=a).json()
        assert model_info["members"] == ["MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0"]

        c1 = client.post("/api/cases", headers=a, json={"title":"Investigation Alpha"}).json()["id"]
        c2 = client.post("/api/cases", headers=a, json={"title":"Investigation Beta"}).json()["id"]
        assert client.patch(f"/api/cases/{c1}", headers=b, json={"title":"Nope", "description":""}).status_code == 404
        assert client.patch(f"/api/cases/{c1}", headers=a, json={"title":"Updated Alpha", "description":"Note"}).status_code == 200
        assert client.get(f"/api/cases/{c1}", headers=a).json()["title"] == "Updated Alpha"

        aid, eid, directory = seed_analysis(client, settings, a, owner_id)
        for cid in (c1, c2):
            assert client.post(f"/api/cases/{cid}/analyses", headers=a,
                               json={"analysis_id":aid}).status_code == 201
        links = client.get("/api/analysis-case-links", headers=a).json()
        assert len(links[aid]) == 2
        assert client.get("/api/analysis-case-links", headers=b).json() == {}
        assert client.delete(f"/api/analyses/{aid}", headers=b, params={"confirm": "true"}).status_code == 404
        assert client.request("DELETE", f"/api/cases/{c1}", headers=a,
                             json={"confirm_title":"wrong", "delete_analyses":True}).status_code == 400
        assert client.request("DELETE", f"/api/cases/{c1}", headers=a,
                             json={"confirm_title":"Updated Alpha", "delete_analyses":True}).status_code == 409
        assert directory.exists() and client.get(f"/api/analyses/{aid}", headers=a).status_code == 200
        assert client.delete(f"/api/cases/{c2}/analyses/{aid}", headers=a).status_code == 200
        assert client.get("/api/analysis-case-links", headers=a).json()[aid][0]["title"] == "Updated Alpha"
        deleted = client.request("DELETE", f"/api/cases/{c1}", headers=a,
                                json={"confirm_title":"Updated Alpha", "delete_analyses":True})
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted_analyses"] == 1
        assert client.get(f"/api/cases/{c1}", headers=a).status_code == 404
        assert client.get(f"/api/analyses/{aid}", headers=a).status_code == 404
        assert not directory.exists()
        assert client.get(f"/api/evidence/{eid}", headers=a).status_code == 200

        another_id, _, another_dir = seed_analysis(client, settings, a, owner_id)
        assert client.delete(f"/api/analyses/{another_id}", headers=a).status_code == 400
        deleted = client.delete(f"/api/analyses/{another_id}", headers=a, params={"confirm": "true"})
        assert deleted.status_code == 200, deleted.text
        assert not another_dir.exists()
