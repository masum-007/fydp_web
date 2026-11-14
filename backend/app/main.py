"""Local-development API. Run with: uvicorn app.main:create_app --factory --reload"""

import hashlib
import json
import secrets
import zipfile
import logging
import shutil
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from PIL import Image as PILImage, ImageOps
from pathlib import Path

import time
from threading import Lock, BoundedSemaphore, Event, Thread

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from .config import Settings
from .database import connection, initialize
from .images import inspect_image
from .schemas import (
    Register,
    Login,
    User,
    Token,
    Evidence,
    AnalyzeRequest,
    CaseCreate,
    CaseAnalysisAdd,
    CaseStatusUpdate,
    CaseEdit,
    CaseDeleteConfirm,
    ProfileUpdate, PasswordUpdate,
)
from .inference_v2 import InferenceEngine
from .report_service import generate_forensic_report
from .explainability_service import generate_explanation, SUPPORTED_METHODS
from .inference_v2 import MODEL_ORDER
from .xai_jobs import XAIJobStore, XAIQueueError, worker_loop


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings.from_env()
    engine = engine or InferenceEngine(settings.model_manifest)
    passwords = PasswordHash.recommended()
    dummy_hash = passwords.hash("unused-timing-comparison-password")
    bearer = HTTPBearer(auto_error=False)
    session_cookie = "neuraledge_session"

    def issue_access_token(user: User, session_id: str) -> Token:
        issued = datetime.now(timezone.utc)
        encoded = jwt.encode(
            {"sub": user.id, "sid": session_id, "iat": issued,
             "exp": issued + timedelta(minutes=30),
             "iss": "neuraledge", "aud": "neuraledge-api"},
            settings.secret, algorithm="HS256",
        )
        return Token(access_token=encoded, user=user)

    def set_session_cookie(response: Response, secret: str) -> None:
        response.set_cookie(
            key=session_cookie, value=secret, httponly=True,
            secure=settings.cookie_secure, samesite="lax", path="/api/auth",
            max_age=settings.remembered_session_days * 86400,
        )
        response.headers["Cache-Control"] = "no-store"

    def reject_untrusted_origin(request: Request) -> None:
        # The browser uses the Next.js same-origin /api rewrite. This check is
        # defense in depth for state-changing cookie-authenticated endpoints.
        origin = request.headers.get("origin")
        if origin and origin not in settings.origins:
            raise HTTPException(403, "Untrusted request origin.")

    def read_session(request: Request) -> tuple[str, User] | None:
        raw = request.cookies.get(session_cookie)
        if not raw or len(raw) > 256:
            return None
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with connection(settings) as db:
            row = db.execute(
                """SELECT s.id, u.id AS user_id, u.name, u.email
                   FROM auth_sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_hash=? AND s.expires_at>?""",
                (digest, now()),
            ).fetchone()
        return (row["id"], User(id=row["user_id"], name=row["name"],
                                email=row["email"])) if row else None

    # Guest inference is opt-in. Enable only for a controlled local demo.
    # Public deployment needs edge rate limiting and additional anti-abuse measures.
    guest_enabled = os.getenv("GUEST_DETECTION_ENABLED", "false").lower() == "true"
    guest_requests: dict[str, list[float]] = {}
    guest_lock = Lock()
    guest_slot = BoundedSemaphore(1)
    xai_jobs = XAIJobStore(settings)
    xai_stop = Event()
    xai_thread = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal xai_thread
        initialize(settings)
        (settings.data_dir / "analyses").mkdir(exist_ok=True)
        xai_jobs.install()
        engine.load()
        # Embedded single worker for local development and single-instance hosting.
        # Set XAI_WORKER_MODE=external on the API server when starting a dedicated
        # "python -m app.xai_worker_cli" process against the SAME persistent data_dir.
        # Never run two workers against a separate/ephemeral filesystem.
        if os.getenv('XAI_WORKER_MODE', 'embedded').strip().lower() == 'embedded':
            xai_stop.clear()
            xai_thread = Thread(
                target=worker_loop,
                args=(settings, engine, xai_stop),
                kwargs={'generator': generate_explanation},
                daemon=True,
                name='neuraledge-xai-worker',
            )
            xai_thread.start()
        try:
            yield
        finally:
            xai_stop.set()
            if xai_thread is not None:
                xai_thread.join(timeout=2)

    app = FastAPI(
        title="NeuralEdge Backend - Stage 2", version="0.2.0", lifespan=lifespan
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )

    def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        unauthorized = HTTPException(
            401,
            "Invalid or expired credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if not credentials:
            raise unauthorized
        try:
            claims = jwt.decode(
                credentials.credentials,
                settings.secret,
                algorithms=["HS256"],
                issuer="neuraledge",
                audience="neuraledge-api",
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.InvalidTokenError:
            raise unauthorized
        if not isinstance(claims.get("sid"), str):
            raise unauthorized
        with connection(settings) as db:
            row = db.execute(
                """SELECT u.id,u.name,u.email FROM users u
                   JOIN auth_sessions s ON s.user_id=u.id
                   WHERE u.id=? AND s.id=? AND s.expires_at>?""",
                (claims["sub"], claims["sid"], now()),
            ).fetchone()
        if not row:
            raise unauthorized
        return User(**dict(row))

    def owned_evidence(evidence_id, user):
        with connection(settings) as db:
            row = db.execute(
                "SELECT * FROM evidence WHERE id=? AND user_id=?",
                (evidence_id, user.id),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Evidence not found.")
        return dict(row)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "inference_ready": engine.ready,
            "inference_reason": engine.reason,
            "stage": "model-integration",
        }

    @app.post("/api/auth/register", response_model=User, status_code=201)
    def register(body: Register):
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Name must not be blank.")
        user = User(id=str(uuid4()), name=name, email=str(body.email).lower())
        hashed = passwords.hash(body.password)
        try:
            with connection(settings) as db:
                db.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?)",
                    (user.id, user.name, user.email, hashed, now()),
                )
                db.execute(
                    "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                    (user.id, "register", now()),
                )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "This email is already registered.")
        return user

    @app.post("/api/auth/login", response_model=Token)
    def login(body: Login, response: Response, request: Request):
        reject_untrusted_origin(request)
        with connection(settings) as db:
            row = db.execute(
                "SELECT * FROM users WHERE email=?", (str(body.email).lower(),)
            ).fetchone()
        valid = passwords.verify(
            body.password, row["password_hash"] if row else dummy_hash
        )
        if not row or not valid:
            raise HTTPException(401, "Incorrect email or password.")
        user = User(**dict(row))
        session_id = str(uuid4())
        secret = secrets.token_urlsafe(32)
        with connection(settings) as db:
            db.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now(),))
            db.execute(
                """INSERT INTO auth_sessions(id,user_id,token_hash,created_at,expires_at)
                   VALUES(?,?,?,?,?)""",
                (session_id, user.id, hashlib.sha256(secret.encode()).hexdigest(),
                 now(), (datetime.now(timezone.utc) +
                         timedelta(days=settings.remembered_session_days)).isoformat()),
            )
            db.execute(
                "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                (user.id, "login", now()),
            )
        set_session_cookie(response, secret)
        return issue_access_token(user, session_id)

    @app.post("/api/auth/refresh", response_model=Token)
    def refresh_session(request: Request, response: Response):
        reject_untrusted_origin(request)
        session = read_session(request)
        if not session:
            raise HTTPException(401, "Session expired. Please log in again.")
        response.headers["Cache-Control"] = "no-store"
        return issue_access_token(session[1], session[0])

    @app.post("/api/auth/logout", status_code=204)
    def logout_session(request: Request, response: Response):
        reject_untrusted_origin(request)
        session = read_session(request)
        if session:
            with connection(settings) as db:
                db.execute("DELETE FROM auth_sessions WHERE id=?", (session[0],))
                db.execute(
                    "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                    (session[1].id, "logout", now()),
                )
        response.delete_cookie(key=session_cookie, path="/api/auth",
                               secure=settings.cookie_secure, httponly=True,
                               samesite="lax")
        response.headers["Cache-Control"] = "no-store"
        response.status_code = 204
        return response

    @app.get("/api/model-info")
    def model_info(user: User = Depends(current_user)):
        """Authenticated display metadata; no secrets or arbitrary manifest paths."""
        members = list(getattr(engine, "models", {}).keys())
        if not members and getattr(engine, "ready", False):
            members = list(MODEL_ORDER)
        return {
            "ready": bool(engine.ready),
            "reason": engine.reason,
            "model": "FourModelStacking" if members and len(members) == 4 else "Unavailable",
            "mode": "stacking" if len(members) == 4 else "unknown",
            "members": members,
            "threshold": getattr(engine, "threshold", None),
            "model_version": getattr(engine, "model_version", None),
            "explainability": ["Grad-CAM", "LIME", "SHAP"],
        }

    @app.get("/api/auth/me", response_model=User)
    def me(user: User = Depends(current_user)):
        return user

    def access_session_id(request: Request, user: User) -> str:
        # current_user already authenticated the exact bearer token and checked
        # its session against the database. Decode once more only to read sid.
        bearer_value = request.headers.get("authorization", "")
        if not bearer_value.lower().startswith("bearer "):
            raise HTTPException(401, "Missing access credentials.")
        try:
            claims = jwt.decode(
                bearer_value[7:].strip(), settings.secret, algorithms=["HS256"],
                issuer="neuraledge", audience="neuraledge-api",
                options={"require": ["sub", "sid", "exp", "iat", "iss", "aud"]},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid access credentials.")
        if claims.get("sub") != user.id or not isinstance(claims.get("sid"), str):
            raise HTTPException(401, "Invalid session ownership.")
        return claims["sid"]

    @app.patch("/api/auth/profile", response_model=User)
    def update_profile(body: ProfileUpdate, user: User = Depends(current_user)):
        name = body.name.strip()
        if len(name) < 2:
            raise HTTPException(422, "Please enter a name of at least two characters.")
        with connection(settings) as db:
            db.execute("UPDATE users SET name=? WHERE id=?", (name, user.id))
            db.execute("INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                       (user.id, "profile_updated", now()))
        return User(id=user.id, name=name, email=user.email)

    @app.get("/api/auth/sessions")
    def active_sessions(request: Request, user: User = Depends(current_user)):
        current_sid = access_session_id(request, user)
        with connection(settings) as db:
            rows = db.execute(
                """SELECT id, created_at, expires_at FROM auth_sessions
                   WHERE user_id=? AND expires_at>? ORDER BY created_at DESC""",
                (user.id, now()),
            ).fetchall()
        return [{"id": r["id"], "created_at": r["created_at"],
                 "expires_at": r["expires_at"], "is_current": r["id"] == current_sid}
                for r in rows]

    @app.post("/api/auth/sessions/revoke-others")
    def revoke_other_sessions(request: Request, user: User = Depends(current_user)):
        sid = access_session_id(request, user)
        with connection(settings) as db:
            cur = db.execute("DELETE FROM auth_sessions WHERE user_id=? AND id<>?",
                             (user.id, sid))
            db.execute("INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                       (user.id, "revoke_other_sessions", now()))
        return {"revoked": cur.rowcount}

    @app.post("/api/auth/sessions/revoke-all", status_code=204)
    def revoke_all_sessions(request: Request, response: Response,
                            user: User = Depends(current_user)):
        access_session_id(request, user)
        with connection(settings) as db:
            db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user.id,))
            db.execute("INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                       (user.id, "revoke_all_sessions", now()))
        response.delete_cookie(key=session_cookie, path="/api/auth",
                               secure=settings.cookie_secure, httponly=True,
                               samesite="lax")
        response.headers["Cache-Control"] = "no-store"
        response.status_code = 204
        return response

    @app.post("/api/auth/password", status_code=204)
    def change_password(body: PasswordUpdate, request: Request, response: Response,
                        user: User = Depends(current_user)):
        access_session_id(request, user)
        with connection(settings) as db:
            row = db.execute("SELECT password_hash FROM users WHERE id=?", (user.id,)).fetchone()
            if not row or not passwords.verify(body.current_password, row["password_hash"]):
                raise HTTPException(400, "Current password is incorrect.")
            if body.current_password == body.new_password:
                raise HTTPException(422, "Choose a different new password.")
            password_hash = passwords.hash(body.new_password)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user.id))
            # Changing a password ends *all* sessions, including this one.
            db.execute("DELETE FROM auth_sessions WHERE user_id=?", (user.id,))
            db.execute("INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                       (user.id, "password_changed", now()))
        response.delete_cookie(key=session_cookie, path="/api/auth",
                               secure=settings.cookie_secure, httponly=True,
                               samesite="lax")
        response.headers["Cache-Control"] = "no-store"
        response.status_code = 204
        return response

    @app.get("/api/model-research")
    def model_research(user: User = Depends(current_user)):
        # Read-only, deployment-bundle-owned metrics: never mix in scores from
        # an older notebook or another threshold/model configuration.
        try:
            manifest = json.loads(settings.model_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"available": False, "reason": "Active deployment does not contain a research metrics record."}
        records = manifest.get("test_set_metrics")
        order = manifest.get("model_order") or []
        if not isinstance(records, list) or not isinstance(order, list):
            return {"available": False, "reason": "Matching research metrics were not bundled with the active models."}
        valid_models = set(order) | {"Stacking_TTA", "SoftVote_TTA"}
        filtered = []
        for entry in records:
            if not isinstance(entry, dict) or entry.get("model") not in valid_models:
                continue
            try:
                if abs(float(entry.get("threshold")) - float(manifest.get("operating_threshold"))) > 1e-8:
                    continue
                metrics = {key: entry[key] for key in (
                    "model", "n", "threshold", "accuracy", "balanced_accuracy",
                    "fake_precision", "fake_recall", "fake_F1", "ROC_AUC", "PR_AUC",
                    "TN", "FP", "FN", "TP") if key in entry}
                filtered.append(metrics)
            except (TypeError, ValueError):
                continue
        return {"available": bool(filtered), "model_order": order, "metrics": filtered,
                "test_count": next((r.get("n") for r in filtered if r.get("model") == "Stacking_TTA"), None),
                "threshold": manifest.get("operating_threshold"),
                "split_counts": manifest.get("split_counts"),
                "research_caveats": manifest.get("research_caveats"),
                "note": "Internal held-out Kaggle research results, not live website accuracy. Robustness must be evaluated separately."}

    @app.post("/api/evidence", response_model=Evidence, status_code=201)
    def upload(file: UploadFile, user: User = Depends(current_user)):
        try:
            data = file.file.read(settings.max_upload_bytes + 1)
        finally:
            file.file.close()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, "Upload exceeds the configured size limit.")
        width, height, media_type = inspect_image(data)
        evidence_id = str(uuid4())
        # Only a UUID is used as a storage filename; submitted names are metadata.
        filename = (file.filename or "image").replace("\\", "/").split("/")[-1]
        filename = "".join(c for c in filename if c.isprintable())[:200] or "image"
        record = Evidence(
            id=evidence_id,
            filename=filename,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            width=width,
            height=height,
            media_type=media_type,
            created_at=now(),
            status="uploaded",
        )
        path = settings.data_dir / "uploads" / evidence_id
        try:
            with path.open("xb") as output:
                output.write(data)
            with connection(settings) as db:
                db.execute(
                    "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        record.id,
                        user.id,
                        record.filename,
                        record.sha256,
                        record.size_bytes,
                        width,
                        height,
                        media_type,
                        record.created_at,
                        record.status,
                    ),
                )
                db.execute(
                    "INSERT INTO audit_events(user_id,action,evidence_id,created_at) VALUES (?,?,?,?)",
                    (user.id, "upload", evidence_id, now()),
                )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return record

    @app.get("/api/evidence", response_model=list[Evidence])
    def list_evidence(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user: User = Depends(current_user),
    ):
        with connection(settings) as db:
            rows = db.execute(
                "SELECT * FROM evidence WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (user.id, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/api/evidence/{evidence_id}", response_model=Evidence)
    def evidence(evidence_id: str, user: User = Depends(current_user)):
        return owned_evidence(evidence_id, user)

    @app.get("/api/evidence/{evidence_id}/thumbnail")
    def evidence_thumbnail(evidence_id: str, user: User = Depends(current_user)):
        record = owned_evidence(evidence_id, user)
        try:
            data = (settings.data_dir / "uploads" / record["id"]).read_bytes()
        except FileNotFoundError:
            raise HTTPException(410, "Original evidence is missing.")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise HTTPException(409, "Evidence integrity check failed.")
        try:
            with PILImage.open(io.BytesIO(data)) as source:
                small = ImageOps.exif_transpose(source).convert("RGB")
                small.thumbnail((200, 200), PILImage.Resampling.LANCZOS)
                output = io.BytesIO()
                small.save(output, format="JPEG", quality=78, optimize=True)
        except (OSError, ValueError):
            raise HTTPException(422, "Evidence cannot be previewed.")
        return Response(content=output.getvalue(), media_type="image/jpeg",
                        headers={"Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff"})

    @app.get("/api/evidence/{evidence_id}/image")
    def original(evidence_id: str, user: User = Depends(current_user)):
        record = owned_evidence(evidence_id, user)
        path = settings.data_dir / "uploads" / record["id"]
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise HTTPException(410, "Original evidence is missing.")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise HTTPException(409, "Evidence integrity check failed.")
        with connection(settings) as db:
            db.execute(
                "INSERT INTO audit_events(user_id,action,evidence_id,created_at) VALUES (?,?,?,?)",
                (user.id, "download", evidence_id, now()),
            )
        return StreamingResponse(
            io.BytesIO(data),
            media_type=record["media_type"],
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def analysis_record(analysis_id, user):
        with connection(settings) as db:
            row = db.execute(
                "SELECT * FROM analyses WHERE id=? AND user_id=?",
                (analysis_id, user.id),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Analysis not found.")
        return json.loads(row["result_json"])

    @app.post("/api/analyze", status_code=201)
    def analyze(body: AnalyzeRequest, user: User = Depends(current_user)):
        record = owned_evidence(body.evidence_id, user)
        if not engine.ready:
            raise HTTPException(
                503,
                {
                    "code": engine.reason,
                    "message": "Inference is unavailable; install verified model artifacts and restart.",
                },
            )
        if record["media_type"] not in {"image/jpeg", "image/png"}:
            raise HTTPException(
                415,
                "Inference currently supports JPEG and PNG. WEBP evidence can be stored but not analyzed.",
            )
        try:
            data = (settings.data_dir / "uploads" / record["id"]).read_bytes()
        except FileNotFoundError:
            raise HTTPException(410, "Original evidence is missing.")
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise HTTPException(409, "Evidence integrity check failed.")
        # Validate again in case files were modified outside the application.
        inspect_image(data)
        try:
            prediction, assets = engine.predict(data)
        except Exception:
            logging.getLogger(__name__).exception("Inference failed")
            raise HTTPException(
                503,
                {
                    "code": "INFERENCE_FAILED",
                    "message": "No completed analysis was saved. Check backend logs.",
                },
            )
        analysis_id = str(uuid4())
        directory = settings.data_dir / "analyses" / analysis_id
        result = {
            **prediction,
            "analysis_id": analysis_id,
            "evidence_id": record["id"],
            "image_sha256": record["sha256"],
            "created_at": now(),
            "status": "completed",
            "assets": {
                name: {
                    "url": f"/api/analyses/{analysis_id}/{name}",
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for name, content in assets.items()
            },
        }
        try:
            directory.mkdir()
            for name, content in assets.items():
                if name not in {"heatmap", "overlay"}:
                    raise ValueError("Unknown explanation asset.")
                (directory / (name + ".png")).write_bytes(content)
            with connection(settings) as db:
                db.execute(
                    "INSERT INTO analyses VALUES (?,?,?,?,?)",
                    (
                        analysis_id,
                        user.id,
                        record["id"],
                        json.dumps(result, allow_nan=False),
                        result["created_at"],
                    ),
                )
                db.execute(
                    "INSERT INTO audit_events(user_id,action,evidence_id,created_at) VALUES (?,?,?,?)",
                    (user.id, "analyze", record["id"], now()),
                )
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return result

    @app.get("/api/analyses")
    def list_analyses(
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user: User = Depends(current_user),
    ):
        with connection(settings) as db:
            rows = db.execute(
                "SELECT result_json FROM analyses WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (user.id, limit, offset),
            ).fetchall()
        return [json.loads(row["result_json"]) for row in rows]

    @app.get("/api/analyses/{analysis_id}")
    def get_analysis(analysis_id: str, user: User = Depends(current_user)):
        return analysis_record(analysis_id, user)

    def validate_explanation_request(analysis_id: str, method: str, user: User):
        if method not in SUPPORTED_METHODS:
            raise HTTPException(404, 'Unknown explanation method.')
        result = analysis_record(analysis_id, user)
        if not engine.ready or not hasattr(engine, 'predict_proba_from_face_crops'):
            raise HTTPException(503, 'Four-model inference is not ready.')
        if (result.get('model') != 'FourModelStacking' or
                result.get('model_version') != getattr(engine, 'model_version', None)):
            raise HTTPException(409, 'Analysis uses another model version. Reanalyze with the current model.')
        return result

    def completed_job_response(analysis_id, method, result):
        existing = result.get('xai', {}).get(method)
        if not existing:
            return None
        asset = result.get('assets', {}).get(method)
        if asset:
            path = settings.data_dir / 'analyses' / analysis_id / f'{method}.png'
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
                raise HTTPException(409, 'Saved explanation failed integrity verification.')
        return {
            'id': None, 'analysis_id': analysis_id, 'method': method,
            'status': 'completed', 'progress': 100, 'message': 'Explanation already saved',
            'created_at': existing.get('created_at'), 'updated_at': existing.get('created_at'),
            'started_at': None, 'finished_at': existing.get('created_at'),
        }

    @app.post('/api/analyses/{analysis_id}/explain/{method}', status_code=202)
    def enqueue_saved_explanation(
        analysis_id: str, method: str, user: User = Depends(current_user),
    ):
        """Enqueue in milliseconds; never keep an HTTP connection open for XAI."""
        result = validate_explanation_request(analysis_id, method, user)
        existing = completed_job_response(analysis_id, method, result)
        if existing:
            return existing
        try:
            return xai_jobs.enqueue(user.id, analysis_id, method)
        except XAIQueueError as exc:
            raise HTTPException(exc.status, exc.detail)

    @app.get('/api/analyses/{analysis_id}/explain/{method}/status')
    def explanation_job_status(
        analysis_id: str, method: str, user: User = Depends(current_user),
    ):
        # Ownership is verified on EVERY status poll; never expose other users' jobs.
        if method not in SUPPORTED_METHODS:
            raise HTTPException(404, 'Unknown explanation method.')
        result = analysis_record(analysis_id, user)
        ready = completed_job_response(analysis_id, method, result)
        if ready:
            return ready
        stored = xai_jobs.read(user.id, analysis_id, method)
        if stored:
            return stored
        return {
            'id': None, 'analysis_id': analysis_id, 'method': method,
            'status': 'not_started', 'progress': 0, 'message': 'Not generated',
            'created_at': None, 'updated_at': None,
            'started_at': None, 'finished_at': None,
        }

    @app.delete('/api/analyses/{analysis_id}/explain/{method}/job')
    def cancel_queued_explanation(
        analysis_id: str, method: str, user: User = Depends(current_user),
    ):
        if method not in SUPPORTED_METHODS:
            raise HTTPException(404, 'Unknown explanation method.')
        analysis_record(analysis_id, user)
        try:
            return xai_jobs.cancel(user.id, analysis_id, method)
        except XAIQueueError as exc:
            raise HTTPException(exc.status, exc.detail)

    @app.get("/api/analyses/{analysis_id}/{asset}")
    def explanation_asset(
        analysis_id: str, asset: str, user: User = Depends(current_user)
    ):
        result = analysis_record(analysis_id, user)
        if asset not in {"heatmap", "overlay", "lime", "shap"} or asset not in result["assets"]:
            raise HTTPException(404, "Explanation asset not found.")
        try:
            content = (
                settings.data_dir
                / "analyses"
                / result["analysis_id"]
                / (asset + ".png")
            ).read_bytes()
        except FileNotFoundError:
            raise HTTPException(410, "Explanation asset is missing.")
        if hashlib.sha256(content).hexdigest() != result["assets"][asset]["sha256"]:
            raise HTTPException(409, "Explanation integrity check failed.")
        return StreamingResponse(
            io.BytesIO(content),
            media_type="image/png",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    def build_forensic_report(analysis_id: str, user: User,
                              case_id: str | None = None) -> tuple[bytes, str]:
        # Verify ownership of this analysis and, optionally, its case membership.
        result = analysis_record(analysis_id, user)
        if case_id is not None:
            with connection(settings) as db:
                linked = db.execute(
                    """SELECT c.title FROM cases c
                       JOIN case_analyses ca ON ca.case_id=c.id
                       WHERE c.id=? AND c.user_id=? AND ca.analysis_id=?""",
                    (case_id, user.id, analysis_id),
                ).fetchone()
            if linked is None:
                raise HTTPException(404, "Analysis is not attached to this case.")
            case_title = linked["title"]
        else:
            case_title = None

        # Obtain the associated evidence with the same ownership check.
        evidence = owned_evidence(result["evidence_id"], user)

        original_path = settings.data_dir / "uploads" / evidence["id"]

        overlay_path = (
            settings.data_dir / "analyses" / result["analysis_id"] / "overlay.png"
        )

        try:
            original = original_path.read_bytes()
            overlay = overlay_path.read_bytes()
        except FileNotFoundError:
            raise HTTPException(
                410,
                "Evidence or explanation image is missing.",
            )

        # Validate evidence integrity before report creation.
        original_hash = hashlib.sha256(original).hexdigest()

        if (
            original_hash != evidence["sha256"]
            or original_hash != result["image_sha256"]
        ):
            raise HTTPException(
                409,
                "Original evidence integrity check failed.",
            )

        # Validate explanation integrity.
        expected_overlay_hash = (
            result.get("assets", {}).get("overlay", {}).get("sha256")
        )

        if (
            not expected_overlay_hash
            or hashlib.sha256(overlay).hexdigest() != expected_overlay_hash
        ):
            raise HTTPException(
                409,
                "Grad-CAM overlay integrity check failed.",
            )

        # Load only explanations generated for this exact analysis. Never
        # substitute sample XAI images from training notebooks.
        optional_explanations = {}
        for method in ("lime", "shap"):
            asset_info = result.get("assets", {}).get(method)
            if not asset_info:
                optional_explanations[method] = None
                continue
            try:
                explanation_png = (
                    settings.data_dir / "analyses" / analysis_id / f"{method}.png"
                ).read_bytes()
            except FileNotFoundError:
                raise HTTPException(410, f"{method.upper()} explanation is missing.")
            if hashlib.sha256(explanation_png).hexdigest() != asset_info["sha256"]:
                raise HTTPException(409, f"{method.upper()} explanation integrity check failed.")
            optional_explanations[method] = explanation_png

        try:
            pdf_bytes = generate_forensic_report(
                result,
                evidence,
                original,
                overlay,
                lime_png=optional_explanations["lime"],
                shap_png=optional_explanations["shap"],
                case_title=case_title,
            )
        except Exception:
            logging.getLogger(__name__).exception("Report generation failed")
            raise HTTPException(
                500,
                "Unable to generate forensic report.",
            )

        return pdf_bytes, evidence["id"]

    @app.get("/api/report/{analysis_id}")
    def download_report(analysis_id: str, case_id: str | None = None,
                        user: User = Depends(current_user)):
        pdf_bytes, evidence_id = build_forensic_report(analysis_id, user, case_id)
        with connection(settings) as db:
            db.execute(
                "INSERT INTO audit_events(user_id,action,evidence_id,created_at) VALUES (?,?,?,?)",
                (user.id, "generate_report", evidence_id, now()),
            )
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="NeuralEdge_{analysis_id}.pdf"',
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/cases/{case_id}/reports.zip")
    def download_case_reports(case_id: str, user: User = Depends(current_user)):
        with connection(settings) as db:
            case = db.execute(
                "SELECT id,title FROM cases WHERE id=? AND user_id=?", (case_id, user.id)
            ).fetchone()
            if not case:
                raise HTTPException(404, "Case not found.")
            rows = db.execute(
                """SELECT a.id FROM case_analyses ca
                   JOIN analyses a ON a.id=ca.analysis_id
                   WHERE ca.case_id=? AND a.user_id=?
                   ORDER BY ca.created_at DESC, a.id DESC""",
                (case_id, user.id),
            ).fetchall()
        if not rows:
            raise HTTPException(409, "This case has no attached analyses to export.")
        if len(rows) > 20:
            raise HTTPException(413, "Bulk export supports at most 20 reports per ZIP.")
        content = io.BytesIO()
        # Generate each PDF through the exact same integrity-checked report path.
        with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as bundle:
            for row in rows:
                report, _ = build_forensic_report(row["id"], user, case_id)
                if len(report) > 15 * 1024 * 1024 or content.tell() > 80 * 1024 * 1024:
                    raise HTTPException(413, "Case report export is too large. Download PDFs individually.")
                bundle.writestr(f"NeuralEdge_{row['id']}.pdf", report)
        if content.tell() > 80 * 1024 * 1024:
            raise HTTPException(413, "Case report ZIP is too large.")
        with connection(settings) as db:
            db.execute(
                "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                (user.id, "export_case_reports", now()),
            )
        return Response(
            content=content.getvalue(), media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="NeuralEdge_Case_{case_id[:8]}.zip"',
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    # ---------------------------------------------------
    # FORENSIC CASE MANAGEMENT
    # ---------------------------------------------------

    @app.post("/api/cases", status_code=201)
    def create_case(
        body: CaseCreate,
        user: User = Depends(current_user),
    ):
        title = body.title.strip()
        if len(title) < 3:
            raise HTTPException(422, "Case title is too short.")

        case_id = str(uuid4())
        created_at = now()

        with connection(settings) as db:
            db.execute(
                """
                INSERT INTO cases
                (id, user_id, title, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    user.id,
                    title,
                    body.description.strip(),
                    "open",
                    created_at,
                ),
            )

        return {
            "id": case_id,
            "title": title,
            "description": body.description.strip(),
            "status": "open",
            "created_at": created_at,
            "analysis_count": 0,
        }

    @app.get("/api/cases")
    def list_cases(user: User = Depends(current_user)):
        with connection(settings) as db:
            rows = db.execute(
                """
                SELECT
                    c.id,
                    c.title,
                    c.description,
                    c.status,
                    c.created_at,
                    COUNT(ca.analysis_id) AS analysis_count
                FROM cases c
                LEFT JOIN case_analyses ca
                    ON ca.case_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC, c.id DESC
                """,
                (user.id,),
            ).fetchall()

        return [dict(row) for row in rows]

    @app.get("/api/cases/{case_id}")
    def get_case(
        case_id: str,
        user: User = Depends(current_user),
    ):
        with connection(settings) as db:
            case = db.execute(
                """
                SELECT id, title, description, status, created_at
                FROM cases
                WHERE id = ? AND user_id = ?
                """,
                (case_id, user.id),
            ).fetchone()

            if not case:
                raise HTTPException(404, "Case not found.")

            rows = db.execute(
                """
                SELECT a.result_json
                FROM case_analyses ca
                JOIN analyses a ON a.id = ca.analysis_id
                WHERE ca.case_id = ? AND a.user_id = ?
                ORDER BY ca.created_at DESC
                """,
                (case_id, user.id),
            ).fetchall()

        return {
            **dict(case),
            "analyses": [json.loads(row["result_json"]) for row in rows],
        }

    @app.post(
        "/api/cases/{case_id}/analyses",
        status_code=201,
    )
    def add_analysis_to_case(
        case_id: str,
        body: CaseAnalysisAdd,
        user: User = Depends(current_user),
    ):
        with connection(settings) as db:
            case = db.execute(
                """
                SELECT id, status
                FROM cases
                WHERE id = ? AND user_id = ?
                """,
                (case_id, user.id),
            ).fetchone()

            if not case:
                raise HTTPException(404, "Case not found.")

            if case["status"] != "open":
                raise HTTPException(
                    409,
                    "Cannot modify a closed case.",
                )

            analysis = db.execute(
                """
                SELECT id
                FROM analyses
                WHERE id = ? AND user_id = ?
                """,
                (body.analysis_id, user.id),
            ).fetchone()

            if not analysis:
                raise HTTPException(
                    404,
                    "Analysis not found.",
                )

            existing = db.execute(
                """
                SELECT 1
                FROM case_analyses
                WHERE case_id = ? AND analysis_id = ?
                """,
                (case_id, body.analysis_id),
            ).fetchone()

            if existing:
                raise HTTPException(
                    409,
                    "Analysis already belongs to this case.",
                )

            db.execute(
                """
                INSERT INTO case_analyses
                (case_id, analysis_id, created_at)
                VALUES (?, ?, ?)
                """,
                (case_id, body.analysis_id, now()),
            )

        return {
            "case_id": case_id,
            "analysis_id": body.analysis_id,
            "status": "added",
        }

    @app.patch("/api/cases/{case_id}/status")
    def update_case_status(
        case_id: str,
        body: CaseStatusUpdate,
        user: User = Depends(current_user),
    ):
        with connection(settings) as db:
            cursor = db.execute(
                """
                UPDATE cases
                SET status = ?
                WHERE id = ? AND user_id = ?
                """,
                (body.status, case_id, user.id),
            )

            if cursor.rowcount == 0:
                raise HTTPException(404, "Case not found.")

        return {
            "id": case_id,
            "status": body.status,
        }

    # -------------------- Case editing, links, and deletion --------------------

    @app.patch("/api/cases/{case_id}")
    def edit_case(case_id: str, body: CaseEdit, user: User = Depends(current_user)):
        title = body.title.strip()
        if len(title) < 3:
            raise HTTPException(422, "Case title must have at least 3 characters.")
        with connection(settings) as db:
            row = db.execute(
                "SELECT id FROM cases WHERE id=? AND user_id=?", (case_id, user.id)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Case not found.")
            db.execute(
                "UPDATE cases SET title=?, description=? WHERE id=? AND user_id=?",
                (title, body.description.strip(), case_id, user.id),
            )
            db.execute(
                "INSERT INTO audit_events(user_id, action, created_at) VALUES (?,?,?)",
                (user.id, "edit_case", now()),
            )
        return {"id": case_id, "title": title, "description": body.description.strip()}

    @app.get("/api/analysis-case-links")
    def analysis_case_links(user: User = Depends(current_user)):
        """Return all case associations for this investigator's analyses."""
        with connection(settings) as db:
            rows = db.execute(
                """SELECT ca.analysis_id, c.id AS case_id, c.title
                   FROM case_analyses ca
                   JOIN cases c ON c.id=ca.case_id
                   JOIN analyses a ON a.id=ca.analysis_id
                   WHERE c.user_id=? AND a.user_id=?
                   ORDER BY c.title COLLATE NOCASE, c.id""",
                (user.id, user.id),
            ).fetchall()
        links = {}
        for row in rows:
            links.setdefault(row["analysis_id"], []).append(
                {"id": row["case_id"], "title": row["title"]}
            )
        return links

    @app.delete("/api/cases/{case_id}/analyses/{analysis_id}")
    def unlink_case_analysis(
        case_id: str, analysis_id: str, user: User = Depends(current_user)
    ):
        with connection(settings) as db:
            case = db.execute(
                "SELECT status FROM cases WHERE id=? AND user_id=?", (case_id, user.id)
            ).fetchone()
            if case is None:
                raise HTTPException(404, "Case not found.")
            if case["status"] != "open":
                raise HTTPException(409, "Reopen the case before removing an analysis.")
            deleted = db.execute(
                """DELETE FROM case_analyses WHERE case_id=? AND analysis_id=?
                   AND EXISTS (SELECT 1 FROM analyses WHERE id=? AND user_id=?)""",
                (case_id, analysis_id, analysis_id, user.id),
            )
            if deleted.rowcount == 0:
                raise HTTPException(404, "Analysis is not attached to this case.")
            db.execute(
                "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                (user.id, "unlink_case_analysis", now()),
            )
        return {"case_id": case_id, "analysis_id": analysis_id, "status": "unlinked"}

    def delete_analysis_records(user, analysis_ids, case_id=None):
        """Delete owned analysis rows and explanation files with rollback staging.

        Original evidence is deliberately retained for provenance. Shared analyses
        are blocked during case cascade deletion. A stand-alone analysis deletion
        unlinks it from any cases. Files are moved to local staging before commit.
        Backups and filesystem snapshots are outside this API's control.
        """
        analysis_ids = list(dict.fromkeys(analysis_ids))
        staged = []
        analysis_root = settings.data_dir / "analyses"
        pending = settings.data_dir / ".delete_pending"
        try:
            with connection(settings) as db:
                for analysis_id in analysis_ids:
                    row = db.execute(
                        "SELECT id FROM analyses WHERE id=? AND user_id=?",
                        (analysis_id, user.id),
                    ).fetchone()
                    if row is None:
                        raise HTTPException(404, "Analysis not found.")
                if analysis_ids:
                    placeholders = ",".join("?" for _ in analysis_ids)
                    active = db.execute(
                        "SELECT analysis_id FROM xai_jobs "
                        f"WHERE analysis_id IN ({placeholders}) "
                        "AND status IN ('queued','running') LIMIT 1",
                        tuple(analysis_ids),
                    ).fetchone()
                    if active:
                        raise HTTPException(
                            409, "An explanation job is queued or running. "
                                 "Wait for completion or cancel the queued job before deletion."
                        )
                if case_id is not None and analysis_ids:
                    placeholders = ",".join("?" for _ in analysis_ids)
                    query = (
                        "SELECT DISTINCT analysis_id FROM case_analyses "
                        f"WHERE analysis_id IN ({placeholders}) AND case_id<>?"
                    )
                    shared = db.execute(query, (*analysis_ids, case_id)).fetchall()
                    if shared:
                        raise HTTPException(
                            409,
                            "Case contains analyses shared with other cases. "
                            "Unlink them from those cases before deleting this case.",
                        )
                # File names are immutable UUIDs from DB records, not user input.
                pending.mkdir(exist_ok=True)
                for analysis_id in analysis_ids:
                    source = analysis_root / analysis_id
                    if source.is_symlink():
                        raise HTTPException(409, "Unsafe analysis asset path.")
                    if source.exists():
                        destination = pending / str(uuid4())
                        source.rename(destination)
                        staged.append((source, destination))
                for analysis_id in analysis_ids:
                    db.execute("DELETE FROM case_analyses WHERE analysis_id=?", (analysis_id,))
                    db.execute(
                        "DELETE FROM analyses WHERE id=? AND user_id=?",
                        (analysis_id, user.id),
                    )
                if case_id is not None:
                    db.execute("DELETE FROM cases WHERE id=? AND user_id=?", (case_id, user.id))
                db.execute(
                    "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                    (user.id, "delete_case_and_analyses" if case_id else "delete_analysis", now()),
                )
        except Exception:
            for source, destination in reversed(staged):
                if destination.exists() and not source.exists():
                    destination.rename(source)
            raise
        # After committed DB deletion, remove staged analysis explanation files.
        for _, destination in staged:
            try:
                shutil.rmtree(destination)
            except OSError:
                logging.getLogger(__name__).exception(
                    "Manual cleanup required for deletion staging: %s", destination
                )
        return len(analysis_ids)

    @app.delete("/api/analyses/{analysis_id}")
    def delete_analysis(
        analysis_id: str,
        confirm: bool = Query(False),
        user: User = Depends(current_user),
    ):
        if not confirm:
            raise HTTPException(400, "Explicit confirmation required.")
        count = delete_analysis_records(user, [analysis_id])
        return {"deleted_analyses": count, "original_evidence_retained": True}

    @app.delete("/api/cases/{case_id}")
    def delete_case(
        case_id: str, body: CaseDeleteConfirm, user: User = Depends(current_user)
    ):
        with connection(settings) as db:
            case = db.execute(
                "SELECT title FROM cases WHERE id=? AND user_id=?", (case_id, user.id)
            ).fetchone()
            if case is None:
                raise HTTPException(404, "Case not found.")
            if body.confirm_title != case["title"] or body.delete_analyses is not True:
                raise HTTPException(400, "Type the exact case title to confirm deletion.")
            linked = db.execute(
                """SELECT ca.analysis_id FROM case_analyses ca
                   JOIN analyses a ON a.id=ca.analysis_id
                   WHERE ca.case_id=? AND a.user_id=?""",
                (case_id, user.id),
            ).fetchall()
            analysis_ids = [row["analysis_id"] for row in linked]
        count = delete_analysis_records(user, analysis_ids, case_id=case_id)
        return {"deleted_case": case_id, "deleted_analyses": count,
                "original_evidence_retained": True}

    @app.post("/api/quick-detect")
    def quick_detect(request: Request, file: UploadFile = File(...)):
        """Opt-in guest demo: no saved evidence, analyses, or explanation assets."""
        if not guest_enabled:
            raise HTTPException(404, "Guest detection is disabled.")

        # A lightweight, in-process limiter for a single-worker local demo.
        # Do not trust X-Forwarded-For from untrusted clients.
        client_ip = request.client.host if request.client else "unknown"
        moment = time.monotonic()
        with guest_lock:
            for ip in list(guest_requests):
                recent = [t for t in guest_requests[ip] if moment - t < 3600]
                if recent:
                    guest_requests[ip] = recent
                else:
                    del guest_requests[ip]
            attempts = guest_requests.setdefault(client_ip, [])
            if len(attempts) >= 3:
                raise HTTPException(429, "Guest limit reached. Try again later.")
            attempts.append(moment)

        if not engine.ready:
            raise HTTPException(503, "AI model is currently unavailable.")

        # Read at most one byte beyond the guest size limit.
        max_bytes = 10 * 1024 * 1024
        try:
            data = file.file.read(max_bytes + 1)
        finally:
            file.file.close()
        if len(data) > max_bytes:
            raise HTTPException(413, "Guest images must be 10 MB or smaller.")

        width, height, media_type = inspect_image(data)
        if media_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(415, "Only JPEG and PNG images are supported.")
        if width * height > 8_000_000:
            raise HTTPException(413, "Guest image dimensions are too large.")

        if not guest_slot.acquire(blocking=False):
            raise HTTPException(503, "Guest detection is busy. Please retry.")
        try:
            prediction, _assets = engine.predict(data)
        except Exception:
            logging.getLogger(__name__).exception("Guest inference failed")
            raise HTTPException(503, "Unable to analyze this image.")
        finally:
            guest_slot.release()

        return {
            "prediction": prediction["prediction"],
            "confidence": prediction["confidence"],
            "fake_probability": prediction["fake_probability"],
            "real_probability": prediction["real_probability"],
            "threshold": prediction["threshold"],
            "model": prediction["model"],
            "note": "AI screening result, not proof of authenticity or manipulation.",
        }

    return app
