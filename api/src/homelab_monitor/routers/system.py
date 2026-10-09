from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.production_health import ProductionHealthService
from homelab_monitor.remote_access import RemoteAccessService
from homelab_monitor.schemas import (
    ProductionHealthResponse,
    ProductionNetworkResponse,
    ProductionRuntimeResponse,
    ProductionStorageResponse,
    RemoteAccessResponse,
)
from homelab_monitor.topology import topology as build_topology

router = APIRouter(prefix="/api/v1/system", tags=["system"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = RemoteAccessService()
health_service = ProductionHealthService(remote_access=service)


@router.get(
    "/remote-access",
    response_model=RemoteAccessResponse,
    dependencies=[READ],
    summary="Read Tailscale remote-access status",
)
def get_remote_access() -> RemoteAccessResponse:
    return service.snapshot()


@router.get(
    "/health",
    response_model=ProductionHealthResponse,
    dependencies=[READ],
    summary="Read production component health and diagnostics",
)
def get_production_health(
    db: Annotated[Session, Depends(get_db)],
) -> ProductionHealthResponse:
    return health_service.health(db)


@router.get(
    "/runtime",
    response_model=ProductionRuntimeResponse,
    dependencies=[READ],
    summary="Read agent, Docker, Telegram, and Tailscale runtime status",
)
def get_production_runtime(
    db: Annotated[Session, Depends(get_db)],
) -> ProductionRuntimeResponse:
    return health_service.runtime(db)


@router.get(
    "/storage",
    response_model=ProductionStorageResponse,
    dependencies=[READ],
    summary="Read production storage status",
)
def get_production_storage() -> ProductionStorageResponse:
    return health_service.storage()


@router.get(
    "/network",
    response_model=ProductionNetworkResponse,
    dependencies=[READ],
    summary="Read production network status",
)
def get_production_network() -> ProductionNetworkResponse:
    return health_service.network()


@router.get(
    "/topology",
    dependencies=[READ],
    summary="Read the homelab topology snapshot",
)
def get_topology(db: Annotated[Session, Depends(get_db)]) -> dict:
    return build_topology(
        health_service.health(db),
        health_service.runtime(db),
        health_service.network(),
    )
