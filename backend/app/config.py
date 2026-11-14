import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    secret: str
    data_dir: Path
    origins: tuple[str, ...] = ('http://localhost:3000', 'http://127.0.0.1:3000')
    model_manifest: Path = Path(__file__).resolve().parent.parent / "artifacts" / "manifest.json"
    max_upload_bytes: int = 10 * 1024 * 1024
    cookie_secure: bool = False
    remembered_session_days: int = 7

    def __post_init__(self):
        if len(self.secret) < 32 or self.secret.startswith('REPLACE_'):
            raise ValueError('Set JWT_SECRET to a random secret of at least 32 characters.')
        if not (1 <= self.remembered_session_days <= 30):
            raise ValueError('REMEMBERED_SESSION_DAYS must be between 1 and 30.')
        if self.max_upload_bytes < 1:
            raise ValueError('MAX_UPLOAD_BYTES must be positive.')

    @classmethod
    def from_env(cls):
        root = Path(__file__).resolve().parent.parent
        load_dotenv(root / '.env')
        return cls(
            model_manifest=root / os.getenv("MODEL_MANIFEST", "artifacts/manifest.json"),
            secret=os.getenv('JWT_SECRET', ''),
            data_dir=root / os.getenv('DATA_DIR', 'storage'),
            origins=tuple(x.strip() for x in os.getenv('FRONTEND_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if x.strip()),
            max_upload_bytes=int(os.getenv('MAX_UPLOAD_BYTES', '10485760')),
            cookie_secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
            remembered_session_days=int(os.getenv('REMEMBERED_SESSION_DAYS', '7')),
        )
