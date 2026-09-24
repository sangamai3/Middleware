from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from ..connectors.base.errors import SangamMWException
from ..connectors.base.registry import registry
from ..metrics import init_metrics, metrics_output
from .routes import ai as ai_routes
from .routes import audit as audit_routes
from .routes import auth as auth_routes
from .routes import connectors as connector_routes
from .routes import executions as execution_routes
from .routes import flows as flow_routes
from .routes import gateway as gateway_routes
from .routes import health as health_routes
from .routes import lineage as lineage_routes
from .routes import portal as portal_routes
from .routes import saml as saml_routes
from .routes import scim as scim_routes
from .routes import notifications as notification_routes
from .routes import insights as insight_routes
from .routes import scheduler as scheduler_routes
from .routes import templates as template_routes
from .routes import users as user_routes

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("sangammw.starting", version="0.1.0")
    registry.load()
    init_metrics()
    logger.info("sangammw.connectors_loaded", count=len(registry.ids()), ids=registry.ids())
    from ..engine.schedule_registry import bootstrap_scheduler, shutdown_scheduler

    try:
        await bootstrap_scheduler()
        logger.info("sangammw.scheduler_started")
    except Exception as exc:
        logger.warning("sangammw.scheduler_start_failed", error=str(exc))
    yield
    await shutdown_scheduler()
    from ..db.base import _engine

    if _engine:
        await _engine.dispose()
    logger.info("sangammw.shutdown")


app = FastAPI(
    title="SangamMW",
    description="Open-source middleware / iPaaS platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SangamMWException)
async def sangam_exception_handler(request: Request, exc: SangamMWException) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "flow_id": exc.flow_id,
            "run_id": exc.run_id,
            "step_id": exc.step_id,
            "retry_behavior": exc.retry_behavior.value,
        },
    )


app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(saml_routes.router, prefix="/api/v1")
app.include_router(connector_routes.router, prefix="/api/v1")
app.include_router(flow_routes.router, prefix="/api/v1")
app.include_router(execution_routes.router, prefix="/api/v1")
app.include_router(template_routes.router, prefix="/api/v1")
app.include_router(user_routes.router, prefix="/api/v1")
app.include_router(audit_routes.router, prefix="/api/v1")
app.include_router(lineage_routes.router, prefix="/api/v1")
app.include_router(ai_routes.router, prefix="/api/v1")
app.include_router(gateway_routes.router, prefix="/api/v1")
app.include_router(portal_routes.router, prefix="/api/v1")
app.include_router(notification_routes.router, prefix="/api/v1")
app.include_router(scheduler_routes.router, prefix="/api/v1")
app.include_router(insight_routes.router, prefix="/api/v1")
app.include_router(health_routes.router)
app.include_router(scim_routes.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "connectors": registry.ids(),
    }


@app.get("/metrics", tags=["system"])
async def metrics() -> Response:
    content, content_type = metrics_output()
    return Response(content=content, media_type=content_type)
