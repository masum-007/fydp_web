"""Local-development API. Run with: uvicorn app.main:create_app --factory --reload"""

import hashlib
import json
import logging
import shutil
import io
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
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
)
from .inference import InferenceEngine
from .report_service import generate_forensic_report


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings.from_env()
    engine = engine or InferenceEngine(settings.model_manifest)
    passwords = PasswordHash.recommended()
    dummy_hash = passwords.hash("unused-timing-comparison-password")
    bearer = HTTPBearer(auto_error=False)

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
        allow_methods=['GET', 'POST', 'PATCH'],
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

    @app.get("/api/analyses/{analysis_id}/{asset}")
    def explanation_asset(
        analysis_id: str, asset: str, user: User = Depends(current_user)
    ):
        result = analysis_record(analysis_id, user)
        if asset not in {"heatmap", "overlay"} or asset not in result["assets"]:
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

        try:
            pdf_bytes = generate_forensic_report(
                result,
                evidence,
                original,
                overlay,
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
            "analyses": [
                json.loads(row["result_json"])
                for row in rows
            ],
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

    return app
