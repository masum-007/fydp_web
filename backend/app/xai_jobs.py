"""SQLite-backed, single-worker XAI queue for NeuralEdge.

The request handler only enqueues work. A worker processes one explanation at a
 time, and clients poll SQLite-backed status. Designed for one FastAPI worker and
persistent local storage. For multi-instance hosting, migrate the same API to a
shared transactional queue + persistent object storage; do not use SQLite on
independent instance filesystems.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4

from .database import connection
from .explainability_service import SUPPORTED_METHODS, generate_explanation

LOG = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class XAIQueueError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


class XAIJobStore:
    def __init__(self, settings):
        self.settings = settings

    def install(self):
        with connection(self.settings) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS xai_jobs (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    method TEXT NOT NULL CHECK (method IN ('gradcam','lime','shap')),
                    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
                    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    UNIQUE(analysis_id, method)
                );
                CREATE INDEX IF NOT EXISTS xai_jobs_order ON xai_jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS xai_jobs_user ON xai_jobs(user_id, status);
            ''')

    @staticmethod
    def _public(row):
        return dict(row) if row is not None else None

    def read(self, user_id: str, analysis_id: str, method: str):
        with connection(self.settings) as db:
            row = db.execute('''SELECT id, analysis_id, method, status, progress, message,
                                      created_at, updated_at, started_at, finished_at
                               FROM xai_jobs WHERE user_id=? AND analysis_id=? AND method=?''',
                             (user_id, analysis_id, method)).fetchone()
        return self._public(row)

    def enqueue(self, user_id: str, analysis_id: str, method: str):
        """Idempotent under concurrent requests; two clients never create two jobs."""
        if method not in SUPPORTED_METHODS:
            raise XAIQueueError(404, 'Unknown explanation method.')
        at = utcnow()
        with connection(self.settings) as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('''SELECT id, status FROM xai_jobs
                                     WHERE user_id=? AND analysis_id=? AND method=?''',
                                  (user_id, analysis_id, method)).fetchone()
            if existing and existing['status'] in ('queued', 'running', 'completed'):
                pass
            else:
                global_count = db.execute("SELECT COUNT(*) FROM xai_jobs WHERE status IN ('queued','running')").fetchone()[0]
                user_count = db.execute("SELECT COUNT(*) FROM xai_jobs WHERE user_id=? AND status IN ('queued','running')", (user_id,)).fetchone()[0]
                if global_count >= 20 or user_count >= 2:
                    raise XAIQueueError(429, 'Explanation queue is full. Check existing jobs and retry later.')
                job_id = str(uuid4())
                if existing:
                    db.execute('''UPDATE xai_jobs SET id=?, status='queued', progress=0,
                                  message='Waiting for explanation worker', created_at=?, updated_at=?,
                                  started_at=NULL, finished_at=NULL
                                  WHERE user_id=? AND analysis_id=? AND method=?''',
                               (job_id, at, at, user_id, analysis_id, method))
                else:
                    db.execute('''INSERT INTO xai_jobs(id,analysis_id,user_id,method,status,
                                  progress,message,created_at,updated_at)
                                  VALUES(?,?,?,?,'queued',0,'Waiting for explanation worker',?,?)''',
                               (job_id, analysis_id, user_id, method, at, at))
        return self.read(user_id, analysis_id, method)

    def claim(self):
        with connection(self.settings) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT * FROM xai_jobs WHERE status='queued'
                                ORDER BY created_at,id LIMIT 1''').fetchone()
            if row is None:
                return None
            at = utcnow()
            db.execute('''UPDATE xai_jobs SET status='running',progress=10,
                          message='Validating evidence',started_at=?,updated_at=?
                          WHERE id=? AND status='queued' ''', (at, at, row['id']))
            return dict(row)

    def update(self, job_id: str, progress: int, message: str):
        with connection(self.settings) as db:
            db.execute('''UPDATE xai_jobs SET progress=?,message=?,updated_at=?
                          WHERE id=? AND status='running' ''',
                       (progress, message, utcnow(), job_id))

    def finish(self, job_id: str, success: bool, message: str):
        with connection(self.settings) as db:
            db.execute('''UPDATE xai_jobs SET status=?,progress=?,message=?,
                          updated_at=?,finished_at=? WHERE id=? AND status='running' ''',
                       ('completed' if success else 'failed', 100 if success else 0,
                        message[:500], utcnow(), utcnow(), job_id))

    def cancel(self, user_id: str, analysis_id: str, method: str):
        with connection(self.settings) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status FROM xai_jobs WHERE user_id=? AND analysis_id=? AND method=?',
                             (user_id, analysis_id, method)).fetchone()
            if row is None:
                raise XAIQueueError(404, 'No explanation job exists.')
            if row['status'] == 'running':
                raise XAIQueueError(409, 'Explanation is already running and cannot be stopped safely.')
            if row['status'] == 'queued':
                db.execute('''UPDATE xai_jobs SET status='cancelled',message='Cancelled before starting',
                              updated_at=?,finished_at=? WHERE user_id=? AND analysis_id=? AND method=?''',
                           (utcnow(), utcnow(), user_id, analysis_id, method))
        return self.read(user_id, analysis_id, method)

    def interrupt_jobs_from_previous_process(self):
        """Call ONLY on the single dedicated worker's startup, not a web-only process."""
        with connection(self.settings) as db:
            db.execute('''UPDATE xai_jobs SET status='failed',progress=0,
                          message='Worker restarted during explanation. Retry this job.',
                          updated_at=?,finished_at=? WHERE status='running' ''',
                       (utcnow(), utcnow()))


def perform_job(settings, engine, job, store: XAIJobStore, *, generator=None):
    """Recheck ownership, exact model version, evidence hash and immutability."""
    generator = generator or generate_explanation
    jid, uid, aid, method = (job['id'], job['user_id'], job['analysis_id'], job['method'])
    with connection(settings) as db:
        row = db.execute('''SELECT a.result_json, e.id evidence_id, e.sha256 evidence_sha
                             FROM analyses a JOIN evidence e ON e.id=a.evidence_id
                             WHERE a.id=? AND a.user_id=? AND e.user_id=?''', (aid, uid, uid)).fetchone()
    if row is None:
        raise ValueError('Analysis or evidence is no longer available.')
    result = json.loads(row['result_json'])
    if not getattr(engine, 'ready', False) or not hasattr(engine, 'predict_proba_from_face_crops'):
        raise ValueError('The four-model inference engine is unavailable.')
    if result.get('model') != 'FourModelStacking' or result.get('model_version') != getattr(engine, 'model_version', None):
        raise ValueError('Analysis model version no longer matches the active deployment. Reanalyze first.')
    current = result.get('xai', {}).get(method)
    if current:
        asset = result.get('assets', {}).get(method)
        if asset:
            path = settings.data_dir / 'analyses' / aid / f'{method}.png'
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
                raise ValueError('Saved explanation asset failed integrity verification.')
        return  # An identical completed explanation already exists.

    original = settings.data_dir / 'uploads' / row['evidence_id']
    if not original.is_file():
        raise ValueError('Original evidence is missing.')
    content = original.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    if sha != row['evidence_sha'] or sha != result.get('image_sha256'):
        raise ValueError('Original evidence failed SHA-256 verification.')

    store.update(jid, 30, 'Generating ' + method.upper() + ' (this can take several minutes)')
    png, metadata = generator(engine, content, method,
                              landmarker_task=os.getenv('FACE_LANDMARKER_TASK'),
                              target_label=result.get('prediction'))
    store.update(jid, 90, 'Saving and verifying explanation')
    metadata['created_at'] = utcnow()
    folder = settings.data_dir / 'analyses' / aid
    image_path = folder / f'{method}.png'
    tmp = folder / f'.{method}.{jid}.tmp'
    asset = None
    if png is not None:
        asset = {'url': f'/api/analyses/{aid}/{method}', 'sha256': hashlib.sha256(png).hexdigest()}
        if image_path.exists():
            raise ValueError('An unexplained existing image file requires integrity review.')
        tmp.write_bytes(png)
    try:
        with connection(settings) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT result_json FROM analyses WHERE id=? AND user_id=?', (aid, uid)).fetchone()
            if row is None:
                raise ValueError('Analysis was deleted during explanation generation.')
            stored = json.loads(row['result_json'])
            if stored.get('xai', {}).get(method):
                raise ValueError('Explanation was saved concurrently; review existing result.')
            if png is not None:
                if image_path.exists():
                    raise ValueError('Explanation image already exists; inspect before retry.')
                os.replace(tmp, image_path)
            stored.setdefault('xai', {})[method] = metadata
            if asset:
                stored.setdefault('assets', {})[method] = asset
            db.execute('UPDATE analyses SET result_json=? WHERE id=? AND user_id=?',
                       (json.dumps(stored, allow_nan=False), aid, uid))
            db.execute('''INSERT INTO audit_events(user_id,action,evidence_id,created_at)
                          VALUES (?,?,?,?)''', (uid, f'explain_{method}', result['evidence_id'], utcnow()))
    finally:
        tmp.unlink(missing_ok=True)


def worker_loop(settings, engine, stop: Event, *, generator=None):
    """One worker per persistent SQLite DB. Queue survives browser disconnects."""
    store = XAIJobStore(settings)
    store.install()
    store.interrupt_jobs_from_previous_process()
    while not stop.is_set():
        try:
            job = store.claim()
            if job is None:
                stop.wait(1)
                continue
            try:
                perform_job(settings, engine, job, store, generator=generator)
            except Exception as exc:
                LOG.exception('Explanation job failed: %s (%s)', job['id'], job['method'])
                # User-facing details are intentionally generic to avoid leaking paths.
                store.finish(job['id'], False,
                             'Explanation failed. Check backend logs and retry. ' +
                             ('Model mismatch.' if 'model version' in str(exc).lower() else ''))
            else:
                store.finish(job['id'], True, 'Explanation saved and ready')
        except (sqlite3.Error, OSError):
            LOG.exception('Explanation worker database/storage error')
            stop.wait(2)
