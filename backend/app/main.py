"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config.settings import get_settings
from app.core.database.engine import dispose_engine
from app.core.database.redis import close_redis
from app.core.logging.structlog_config import configure_logging
from app.shared.exceptions.handlers import register_exception_handlers

log = structlog.get_logger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(settings.log_level, settings.log_format)
    log.info("application_startup", env=settings.app_env, version=settings.app_version)
    yield
    await dispose_engine()
    await close_redis()
    log.info("application_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API de gestão operacional de transportadora",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Custom middleware (order matters: last added = first executed on request)
    from app.api.v1.middleware.audit_middleware import AuditMiddleware
    from app.api.v1.middleware.logging_middleware import LoggingMiddleware
    app.add_middleware(AuditMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    # CORS last = outermost; ensures error responses include Access-Control-Allow-Origin
    cors_kwargs: dict = {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.is_development:
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Exception handlers
    register_exception_handlers(app)

    # Routers
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    from app.modules.auth.router import router as auth_router
    from app.modules.clients.router import router as clients_router
    from app.modules.dashboard.router import router as dashboard_router
    from app.modules.drivers.router import router as drivers_router
    from app.modules.finance.router import router as finance_router
    from app.modules.freights.router import router as freights_router
    from app.modules.maintenance.router import router as maintenance_router
    from app.modules.tracking.router import router as tracking_router
    from app.modules.trucks.router import router as trucks_router
    from app.modules.users.router import router as users_router

    prefix = "/api/v1"
    for router in [
        auth_router,
        users_router,
        drivers_router,
        trucks_router,
        clients_router,
        freights_router,
        maintenance_router,
        finance_router,
        tracking_router,
        dashboard_router,
    ]:
        app.include_router(router, prefix=prefix)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "version": settings.app_version}


app = create_app()
