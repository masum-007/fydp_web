import sqlite3
from contextlib import contextmanager


@contextmanager
def connection(settings):
    db = sqlite3.connect(settings.data_dir / 'app.db', timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / 'uploads').mkdir(exist_ok=True)
    with connection(settings) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            filename TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            width INTEGER NOT NULL, height INTEGER NOT NULL, media_type TEXT NOT NULL,
            created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'uploaded'
        );
        CREATE INDEX IF NOT EXISTS evidence_owner ON evidence(user_id, created_at);
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            evidence_id TEXT NOT NULL REFERENCES evidence(id),
            result_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS analyses_owner ON analyses(user_id, created_at);
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            action TEXT NOT NULL, evidence_id TEXT, created_at TEXT NOT NULL
        );
        ''')
