"""Rate limiting utilities for the Pokemon streaming proxy service."""

import os
import logging

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("pokemon-proxy")

# Get rate limits from environment variables or use defaults
DEFAULT_RATE_LIMIT = os.environ.get("DEFAULT_RATE_LIMIT", "120/minute")
STREAM_RATE_LIMIT = os.environ.get("STREAM_RATE_LIMIT", "100/minute")

logger.info(f"Using rate limits: DEFAULT={DEFAULT_RATE_LIMIT}, STREAM={STREAM_RATE_LIMIT}")

# Create rate limiter
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE", None)
)

def setup_limiter(app: FastAPI) -> None:
    """Configure rate limiting for a FastAPI application.
    
    Args:
        app: The FastAPI application to configure
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    
    logger.info("Rate limiting configured") 