"""Web service entrypoint for Minions Army."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import minions_army.infrastructure.api.routes as routes
import minions_army.infrastructure.observability.logging_config as _logging_config  # noqa: F401
from minions_army.core.runtime.logging import log_event
from minions_army.infrastructure.api.middleware import LoggingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event(logger, logging.INFO, "web.app.started", app_name=app.title, version=app.version)
    yield


app = FastAPI(
    title="Minions Army API",
    version="0.1.0",
    description="Minions Army - A FastAPI-based microservice",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.include_router(routes.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
