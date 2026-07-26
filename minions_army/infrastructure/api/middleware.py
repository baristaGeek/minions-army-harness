"""API middleware examples."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from minions_army.core.runtime.logging import log_event

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log details."""
        log_event(
            logger,
            logging.INFO,
            "http.request.started",
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
        )
        response = await call_next(request)
        log_event(
            logger,
            logging.INFO,
            "http.request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response
