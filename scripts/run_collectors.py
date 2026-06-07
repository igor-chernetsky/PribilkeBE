#!/usr/bin/env python3
"""Run all collectors once (useful for local dev without Celery)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pribilka.db.base import Base
from pribilka.db.session import SessionLocal, engine
from pribilka.workers.tasks import COLLECTOR_MAP, run_collector

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)

    for key in COLLECTOR_MAP:
        result = run_collector(key)
        print(f"{key}: {result}")
