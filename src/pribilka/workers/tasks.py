import logging

from pribilka.collectors.bond_collector import PolandBondCollector
from pribilka.collectors.deposit_collector import PolandDepositCollector
from pribilka.collectors.fx_collector import NbpFxCollector
from pribilka.collectors.gold_collector import PolandGoldCollector
from pribilka.db.session import SessionLocal
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

    logger.info("Running collector %s", collector_key)
    records = collector.collect()

    db = SessionLocal()
    try:
        count = ingest_fn(db, records)
    finally:
        db.close()

    logger.info("Collector %s ingested %d records", collector_key, count)
    return {"collector": collector_key, "ingested": count}
