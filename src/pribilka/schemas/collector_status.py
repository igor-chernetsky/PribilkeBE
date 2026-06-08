from datetime import datetime

from pydantic import BaseModel


class ParserStatusItem(BaseModel):
    parser_name: str
    institution_name: str
    status: str
    offer_count: int
    error_message: str | None = None
    alert_on_empty: bool = True


class CollectorStatusItem(BaseModel):
    collector_key: str
    source_name: str
    status: str
    records_collected: int
    ingested_count: int
    finished_at: datetime
    duration_ms: int
    error_message: str | None = None
    parsers: list[ParserStatusItem] | None = None


class CollectorStatusResponse(BaseModel):
    collectors: list[CollectorStatusItem]
