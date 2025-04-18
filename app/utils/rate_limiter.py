"""Rate limiting utilities for the Pokemon streaming proxy service."""

import os
import logging
import time

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("pokemon-proxy")

# Get rate limits from environment variables or use defaults
DEFAULT_RATE_LIMIT = os.environ.get("DEFAULT_RATE_LIMIT", "120/minute")
STREAM_RATE_LIMIT = os.environ.get("STREAM_RATE_LIMIT", "100/minute")

logger.info(f"Using rate limits: DEFAULT={DEFAULT_RATE_LIMIT}, STREAM={STREAM_RATE_LIMIT}")

# Create a more fault-tolerant key function that falls back to a timestamp if IP can't be determined
def get_client_identifier(request: Request) -> str:
    """Get a client identifier, falling back to timestamp if IP address can't be determined.
    
    Args:
        request: The incoming request
        
    Returns:
        str: The client identifier
    """
    try:
        # Try to get the remote address
        remote_addr = get_remote_address(request)
        if remote_addr:
            return remote_addr
    except Exception as e:
        logger.warning(f"Error getting remote address: {str(e)}")
    
    # Fall back to a timestamp-based identifier (less secure but prevents errors)
    return f"client_{int(time.time())}"

# Create rate limiter with more fault tolerance
limiter = Limiter(
    key_func=get_client_identifier, 
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE", None)
)

# Custom rate limit exceeded handler that logs the error and returns a friendlier message
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors with more detailed logging.
    
    Args:
        request: The incoming request
        exc: The exception that was raised
        
    Returns:
        Response: The error response
    """
    logger.warning(
        f"Rate limit exceeded: {exc.detail} for "
        f"IP: {get_client_identifier(request)}, "
        f"Path: {request.url.path}"
    )
    return await _rate_limit_exceeded_handler(request, exc)

def setup_limiter(app: FastAPI) -> None:
    """Configure rate limiting for a FastAPI application with enhanced error handling.
    
    Args:
        app: The FastAPI application to configure
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
    
    # Add middleware with increased tolerance for errors
    try:
        app.add_middleware(SlowAPIMiddleware)
        logger.info("Rate limiting configured with SlowAPIMiddleware")
    except Exception as e:
        logger.error(f"Error configuring rate limiting middleware: {str(e)}")
        logger.warning("Application will continue without rate limiting")
    
    logger.info("Rate limiting configuration complete") 