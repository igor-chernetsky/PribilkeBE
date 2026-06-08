import logging
import time

from pribilka.collectors.bond_collector import PolandBondCollector
from pribilka.collectors.deposit_collector import PolandDepositCollector
from pribilka.collectors.fx_collector import NbpFxCollector
from pribilka.collectors.gold_collector import PolandGoldCollector
from pribilka.db.session import SessionLocal
from pribilka.services.collector_status import save_collector_run
from pribilka.services.ingestion import ingest_bonds, ingest_deposits, ingest_fx, ingest_gold
from pribilka.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

COLLECTOR_MAP = {
    "deposit": (PolandDepositCollector, ingest_deposits),
    "bond": (PolandBondCollector, ingest_bonds),
    "fx": (NbpFxCollector, ingest_fx),
    "gold": (PolandGoldCollector, ingest_gold),
}


@celery_app.task(name="pribilka.workers.tasks.run_collector")
def run_collector(collector_key: str) -> dict:
    if collector_key not in COLLECTOR_MAP:
        raise ValueError(f"Unknown collector: {collector_key}")

    collector_cls, ingest_fn = COLLECTOR_MAP[collector_key]
    collector = collector_cls()
    source_name = collector.config.source_name

    started = time.monotonic()
    records: list[dict] = []
    ingested = 0
    status = "ok"
    error_message: str | None = None
    parser_results = None

    logger.info("Running collector %s", collector_key)
    try:
        records = collector.collect()
        if hasattr(collector, "last_results"):
            parser_results = collector.last_results

        db = SessionLocal()
        try:
            ingested = ingest_fn(db, records)
        finally:
            db.close()

        if not records:
            status = "empty"
    except Exception as exc:
        status = "error"
        error_message = str(exc)
        logger.exception("Collector %s failed", collector_key)
        raise
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        save_collector_run(
            collector_key=collector_key,
            source_name=source_name,
            status=status,
            records_collected=len(records),
            ingested_count=ingested,
            duration_ms=duration_ms,
            error_message=error_message,
            parser_results=parser_results,
        )

    logger.info("Collector %s ingested %d records", collector_key, ingested)
    return {"collector": collector_key, "ingested": ingested, "status": status}
