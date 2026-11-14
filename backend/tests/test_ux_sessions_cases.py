"""Regression coverage for remembered login, case report export and secure previews.
Run: python -m pytest tests/test_ux_sessions_cases.py -q
"""
import hashlib
import io
import json
import zipfile
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from PIL import Image
from app.config import Settings
from app.database import connection
from app.main import create_app


class ReadyStub:
    ready = True
    reason = None
    models = {n: object() for n in ("MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0")}
    def load(self):
        pass


def example_png():
    output = io.BytesIO()
    Image.new("RGB", (20, 18), "blue").save(output, format="PNG")
    return output.getvalue()


def start_client(tmp_path):
    config = Settings(secret="test-only-" + "x" * 48, data_dir=tmp_path,
                      model_manifest=tmp_path / "missing.json", max_upload_bytes=200000)
    return TestClient(create_app(config, engine=ReadyStub())), config


def register_login(client, email):
    password = "a sufficiently strong testing password"
    assert client.post("/api/auth/register", json={"name": "Investigator", "email": email,
                                                   "password": password}).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": password},
                           headers={"origin": "http://localhost:3000"})
    assert response.status_code == 200, response.text
    return response


def seed_analysis(client, settings, headers, *, case_id=None):
    image = example_png()
    evidence_response = client.post("/api/evidence", headers=headers,
                                    files={"file": ("proof.png", image, "image/png")})
    assert evidence_response.status_code == 201, evidence_response.text
    evidence_id = evidence_response.json()["id"]
    owner_id = client.get("/api/auth/me", headers=headers).json()["id"]
    analysis_id = str(uuid4())
    directory = settings.data_dir / "analyses" / analysis_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "overlay.png").write_bytes(image)
    result = {
        "analysis_id": analysis_id, "evidence_id": evidence_id,
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "assets": {"overlay": {"url": f"/api/analyses/{analysis_id}/overlay",
                               "sha256": hashlib.sha256(image).hexdigest()}},
        "prediction": "Fake", "confidence": .8, "fake_probability": .8,
        "threshold": .5, "model": "FourModelStacking",
        "created_at": "2026-11-14T12:00:00+00:00",
    }
    with connection(settings) as db:
        db.execute("INSERT INTO analyses VALUES (?,?,?,?,?)",
                   (analysis_id, owner_id, evidence_id, json.dumps(result), result["created_at"]))
    if case_id:
        linked = client.post(f"/api/cases/{case_id}/analyses", headers=headers,
                             json={"analysis_id": analysis_id})
        assert linked.status_code == 201, linked.text
    return analysis_id, evidence_id


def test_cookie_restore_access_expiry_logout_and_csrf(tmp_path):
    client, settings = start_client(tmp_path)
    with client:
        assert client.post("/api/auth/refresh").status_code == 401
        login = register_login(client, "owner@example.com")
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=lax" in login.headers["set-cookie"].lower()
        assert "path=/api/auth" in login.headers["set-cookie"].lower()
        assert "neuraledge_session" not in login.text
        token = login.json()["access_token"]
        claims = jwt.decode(token, settings.secret, algorithms=["HS256"],
                            issuer="neuraledge", audience="neuraledge-api")
        assert "sid" in claims
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        # A fresh browser view can request a new short-lived token using the cookie.
        refreshed = client.post("/api/auth/refresh", headers={"origin": "http://localhost:3000"})
        assert refreshed.status_code == 200
        assert refreshed.json()["user"]["email"] == "owner@example.com"
        assert client.post("/api/auth/refresh", headers={"origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/auth/logout", headers={"origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/auth/logout").status_code == 204
        assert client.post("/api/auth/refresh").status_code == 401
        # A still-unexpired access JWT is also revoked immediately by session deletion.
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        assert client.post("/api/auth/logout").status_code == 204


def test_ownership_safe_thumbnails_pdf_and_case_zip(tmp_path, monkeypatch):
    client, settings = start_client(tmp_path)
    import app.main as api_module
    reports = []
    def fake_report(result, evidence, original, overlay, **kwargs):
        assert hashlib.sha256(original).hexdigest() == evidence["sha256"]
        reports.append(kwargs.get("case_title"))
        return b"%PDF-1.4\n%NeuralEdge test PDF\n" + result["analysis_id"].encode()
    monkeypatch.setattr(api_module, "generate_forensic_report", fake_report)
    with client:
        a = register_login(client, "one@example.com")
        token_a = {"Authorization": "Bearer " + a.json()["access_token"]}
        case = client.post("/api/cases", headers=token_a,
                           json={"title": "Impersonation Investigation"})
        assert case.status_code == 201
        case_id = case.json()["id"]
        ids = [seed_analysis(client, settings, token_a, case_id=case_id) for _ in range(2)]
        analysis_id, evidence_id = ids[0]
        thumbnail = client.get(f"/api/evidence/{evidence_id}/thumbnail", headers=token_a)
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"] == "image/jpeg"
        with Image.open(io.BytesIO(thumbnail.content)) as image:
            assert max(image.size) <= 200
        assert thumbnail.headers.get("cache-control") == "no-store"
        pdf = client.get(f"/api/report/{analysis_id}", headers=token_a)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        assert reports[-1] is None
        pdf_case = client.get(f"/api/report/{analysis_id}?case_id={case_id}", headers=token_a)
        assert pdf_case.status_code == 200
        assert reports[-1] == "Impersonation Investigation"
        assert client.get(f"/api/report/{analysis_id}?case_id={uuid4()}", headers=token_a).status_code == 404
        data = client.get(f"/api/cases/{case_id}/reports.zip", headers=token_a)
        assert data.status_code == 200
        with zipfile.ZipFile(io.BytesIO(data.content)) as archive:
            assert len(archive.namelist()) == 2
            assert all(name.endswith(".pdf") for name in archive.namelist())
            assert all(archive.read(name).startswith(b"%PDF-") for name in archive.namelist())
        assert reports[-2:] == ["Impersonation Investigation"] * 2
        # Closing a case still permits report retrieval.
        assert client.patch(f"/api/cases/{case_id}/status", headers=token_a,
                            json={"status": "closed"}).status_code == 200
        assert client.get(f"/api/cases/{case_id}/reports.zip", headers=token_a).status_code == 200
        b = register_login(client, "two@example.com")
        token_b = {"Authorization": "Bearer " + b.json()["access_token"]}
        assert client.get(f"/api/cases/{case_id}/reports.zip", headers=token_b).status_code == 404
        assert client.get(f"/api/evidence/{evidence_id}/thumbnail", headers=token_b).status_code == 404
        assert client.get(f"/api/report/{analysis_id}?case_id={case_id}", headers=token_b).status_code == 404
        # Evidence integrity is checked before returning a thumbnail or PDF.
        (settings.data_dir / "uploads" / evidence_id).write_bytes(b"tampered")
        assert client.get(f"/api/evidence/{evidence_id}/thumbnail", headers=token_a).status_code == 409
        assert client.get(f"/api/report/{analysis_id}", headers=token_a).status_code == 409
        assert client.get(f"/api/cases/{case_id}/reports.zip", headers=token_a).status_code == 409


def test_bulk_export_empty_and_limit(tmp_path, monkeypatch):
    client, settings = start_client(tmp_path)
    with client:
        login = register_login(client, "owner@example.com")
        auth = {"Authorization": "Bearer " + login.json()["access_token"]}
        case_id = client.post("/api/cases", headers=auth,
                              json={"title": "A collection"}).json()["id"]
        assert client.get(f"/api/cases/{case_id}/reports.zip", headers=auth).status_code == 409
        # Create 21 distinct analysis records linked to a single case.
        account_id = login.json()["user"]["id"]
        evidence_id = seed_analysis(client, settings, auth)[1]
        with connection(settings) as db:
            for _ in range(21):
                aid = str(uuid4())
                db.execute("INSERT INTO analyses VALUES (?,?,?,?,?)",
                           (aid, account_id, evidence_id, json.dumps({"analysis_id": aid}), "2026-11-14"))
                db.execute("INSERT INTO case_analyses VALUES (?,?,?)", (case_id, aid, "2026-11-14"))
        assert client.get(f"/api/cases/{case_id}/reports.zip", headers=auth).status_code == 413
