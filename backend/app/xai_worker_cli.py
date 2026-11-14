"""Optional single dedicated XAI worker: python -m app.xai_worker_cli.

Set XAI_WORKER_MODE=external on the API server to avoid embedded processing.
Both API and worker must share a persistent SQLite database and evidence files.
Do NOT run multiple workers against the same SQLite DB without deploying a
proper distributed queue / lease mechanism.
"""
from __future__ import annotations

import logging
from threading import Event

from .config import Settings
from .database import initialize
from .inference_v2 import InferenceEngine
from .xai_jobs import worker_loop


def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    initialize(settings)
    engine = InferenceEngine(settings.model_manifest)
    engine.load()
    if not engine.ready:
        raise RuntimeError('Inference engine is not ready. Cannot start XAI worker.')
    stop = Event()
    try:
        worker_loop(settings, engine, stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == '__main__':
    main()
