from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from pribilka.models.enums import AssetClass


class InsightResponse(BaseModel):
    product_id: UUID
    asset_class: AssetClass
    summary: str
    highlights: list[str]
    generated_at: datetime
    source: str
