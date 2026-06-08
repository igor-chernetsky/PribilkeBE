from fastapi import APIRouter, Depends

from pribilka.api.admin_deps import require_admin_api_key
from pribilka.schemas.collector_status import CollectorStatusItem, CollectorStatusResponse
from pribilka.services.collector_status import list_collector_statuses

router = APIRouter(dependencies=[Depends(require_admin_api_key)])


@router.get("/collector-status", response_model=CollectorStatusResponse)
def collector_status() -> CollectorStatusResponse:
    """Last run snapshot for each registered collector (stored in Redis)."""
    snapshots = list_collector_statuses()
    collectors = [CollectorStatusItem(**snapshot) for snapshot in snapshots]
    return CollectorStatusResponse(collectors=collectors)
