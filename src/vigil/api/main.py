# SPDX-License-Identifier: Apache-2.0
"""FastAPI application factory and entry point."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vigil import MODEL_VERSION
from vigil.agents.a2a import build_a2a_apps
from vigil.agents.runtime import AgentRuntime
from vigil.api.errors import install_handlers
from vigil.api.routes import agents, meta, network, payments, risk
from vigil.api.security import SecurityMiddleware
from vigil.config import Settings, get_settings
from vigil.obs import configure_logging
from vigil.services import Services

log = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """Builds the app. Tests pass their own settings/services."""
    settings = settings or get_settings()
    configure_logging(os.environ.get("VIGIL_LOG_LEVEL", "INFO"))
    svc = services or Services(settings)
    runtime = AgentRuntime(svc)
    a2a_apps = build_a2a_apps(svc, settings.public_base_url) if settings.a2a_enabled else {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for sub in a2a_apps.values():
                await stack.enter_async_context(sub.router.lifespan_context(sub))
                # Insert before the static mount so agent cards and RPC routes win.
                app.router.routes[0:0] = list(sub.router.routes)
            log.info(
                "started",
                extra={"model_version": MODEL_VERSION, "env": settings.env, "agents": runtime.mode},
            )
            yield

    app = FastAPI(
        title="Vigil API",
        version=MODEL_VERSION,
        description="Scam interception, mule-network investigation and AI-agent payment safety. Demo data is synthetic.",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.env != "prod" else None,
    )
    app.state.services = svc
    app.state.runtime = runtime
    install_handlers(app)
    for r in (risk.router, network.router, payments.router, agents.router, meta.router):
        app.include_router(r)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["X-API-Key", "Content-Type", "X-Request-ID"],
            max_age=600,
        )
    app.add_middleware(SecurityMiddleware, settings=settings)
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()


def main() -> None:
    """``vigil-serve`` entry point (Cloud Run sets ``PORT``)."""
    uvicorn.run(
        "vigil.api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
