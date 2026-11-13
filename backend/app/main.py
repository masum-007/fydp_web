"""Local-development API. Run with: uvicorn app.main:create_app --factory --reload"""

import hashlib
import json
import logging
import shutil
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pathlib import Path

import time
from threading import Lock, BoundedSemaphore

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
)
from .inference_v2 import InferenceEngine
from .report_service import generate_forensic_report
from .explainability_service import generate_explanation, SUPPORTED_METHODS
from .inference_v2 import MODEL_ORDER


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings.from_env()
    engine = engine or InferenceEngine(settings.model_manifest)
    passwords = PasswordHash.recommended()
    dummy_hash = passwords.hash("unused-timing-comparison-password")
    bearer = HTTPBearer(auto_error=False)

    # Guest inference is opt-in. Enable only for a controlled local demo.
    # Public deployment needs edge rate limiting and additional anti-abuse measures.
    guest_enabled = os.getenv("GUEST_DETECTION_ENABLED", "false").lower() == "true"
    guest_requests: dict[str, list[float]] = {}
    guest_lock = Lock()
    guest_slot = BoundedSemaphore(1)
    xai_slot = BoundedSemaphore(1)  # One slow explanation at a time per worker.

    @asynccontextmanager
    async def lifespan(app):
        initialize(settings)
        (settings.data_dir / "analyses").mkdir(exist_ok=True)
        engine.load()
        yield

    app = FastAPI(
        title="NeuralEdge Backend - Stage 2", version="0.2.0", lifespan=lifespan
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
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
        with connection(settings) as db:
            row = db.execute(
                "SELECT id,name,email FROM users WHERE id=?", (claims["sub"],)
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
    def login(body: Login):
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
        issued = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": user.id,
                "iat": issued,
                "exp": issued + timedelta(minutes=30),
                "iss": "neuraledge",
                "aud": "neuraledge-api",
            },
            settings.secret,
            algorithm="HS256",
        )
        with connection(settings) as db:
            db.execute(
                "INSERT INTO audit_events(user_id,action,created_at) VALUES (?,?,?)",
                (user.id, "login", now()),
            )
        return Token(access_token=token, user=user)

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

    @app.post("/api/analyses/{analysis_id}/explain/{method}")
    def generate_saved_explanation(
        analysis_id: str,
        method: str,
        user: User = Depends(current_user),
    ):
        """Generate an OPTIONAL explanation only for the owning investigator.

        Prototype endpoint is synchronous. For public deployment replace with
        a persistent job queue and quota-aware worker. Guest users cannot call it.
        """
        if method not in SUPPORTED_METHODS:
            raise HTTPException(404, "Unknown explanation method.")
        result = analysis_record(analysis_id, user)
        if not engine.ready or not hasattr(engine, "predict_proba_from_face_crops"):
            raise HTTPException(503, "Four-model inference is not ready.")
        if (result.get("model") != "FourModelStacking" or
                result.get("model_version") != getattr(engine, "model_version", None)):
            raise HTTPException(
                409,
                "This analysis was generated by a different model version. "
                "Reanalyze the original image with the current model first.",
            )

        # Avoid unnecessary expensive regeneration of explanations.
        existing = result.get("xai", {}).get(method)
        if existing:
            asset = result.get("assets", {}).get(method)
            if asset:
                asset_path = settings.data_dir / "analyses" / analysis_id / f"{method}.png"
                if not asset_path.is_file() or hashlib.sha256(asset_path.read_bytes()).hexdigest() != asset["sha256"]:
                    raise HTTPException(409, "Previously generated explanation failed integrity verification.")
            return {"analysis_id": analysis_id, "method": method, "explanation": existing, "asset": asset}

        # Only one slow request per worker. Not a distributed/global rate limiter.
        if not xai_slot.acquire(blocking=False):
            raise HTTPException(503, "Another explanation is running. Retry after it completes.")
        try:
            evidence = owned_evidence(result["evidence_id"], user)
            try:
                original = (settings.data_dir / "uploads" / evidence["id"]).read_bytes()
            except FileNotFoundError:
                raise HTTPException(410, "Original evidence is missing.")
            original_hash = hashlib.sha256(original).hexdigest()
            if (original_hash != evidence["sha256"] or
                    original_hash != result["image_sha256"]):
                raise HTTPException(409, "Original evidence failed SHA-256 verification.")

            landmarker_task = os.getenv("FACE_LANDMARKER_TASK")
            try:
                image_png, meta = generate_explanation(
                    engine, original, method, landmarker_task=landmarker_task, target_label=result.get("prediction"),
                )
            except Exception:
                logging.getLogger(__name__).exception("XAI generation failed: %s", method)
                raise HTTPException(503, "Unable to generate this explanation. Check backend logs.")
            meta["created_at"] = now()
            folder = settings.data_dir / "analyses" / analysis_id
            asset = None
            if image_png is not None:
                asset = {
                    "url": f"/api/analyses/{analysis_id}/{method}",
                    "sha256": hashlib.sha256(image_png).hexdigest(),
                }
                # Each explanation is immutable; write only the first time.
                try:
                    with (folder / f"{method}.png").open("xb") as output:
                        output.write(image_png)
                except FileExistsError:
                    raise HTTPException(409, "An explanation file already exists; verify before retrying.")

            # Preserve existing analysis fields and any other explanation methods.
            with connection(settings) as db:
                row = db.execute(
                    "SELECT result_json FROM analyses WHERE id=? AND user_id=?",
                    (analysis_id, user.id),
                ).fetchone()
                if row is None:
                    raise HTTPException(404, "Analysis not found.")
                stored = json.loads(row["result_json"])
                stored.setdefault("xai", {})[method] = meta
                if asset:
                    stored.setdefault("assets", {})[method] = asset
                db.execute(
                    "UPDATE analyses SET result_json=? WHERE id=? AND user_id=?",
                    (json.dumps(stored, allow_nan=False), analysis_id, user.id),
                )
                db.execute(
                    "INSERT INTO audit_events(user_id,action,evidence_id,created_at) VALUES (?,?,?,?)",
                    (user.id, f"explain_{method}", evidence["id"], now()),
                )
            return {"analysis_id": analysis_id, "method": method, "explanation": meta, "asset": asset}
        finally:
            xai_slot.release()

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

    @app.get("/api/report/{analysis_id}")
    def download_report(
        analysis_id: str,
        user: User = Depends(current_user),
    ):
        # Check that this analysis belongs to the logged-in user.
        result = analysis_record(analysis_id, user)

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
            )
        except Exception:
            logging.getLogger(__name__).exception("Report generation failed")
            raise HTTPException(
                500,
                "Unable to generate forensic report.",
            )

        with connection(settings) as db:
            db.execute(
                """
                INSERT INTO audit_events
                (user_id, action, evidence_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user.id,
                    "generate_report",
                    evidence["id"],
                    now(),
                ),
            )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="NeuralEdge_{analysis_id}.pdf"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
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
