"""Main FastAPI application for the Pokemon streaming proxy service."""

import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.utils.rate_limiter import limiter, setup_limiter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pokemon-proxy")

# Create FastAPI app
app = FastAPI(
    title="Pokemon Streaming Proxy",
    description="A proxy service for Guardio's Pokemon streaming API",
    version="1.0.0",
)

# Set up rate limiting
setup_limiter(app)

# Include router
app.include_router(router)

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker healthcheck."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)

# Global httpx client
http_client = None


@app.on_event("startup")
async def startup_event():
    """Initialize resources on application startup."""
    global http_client
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info("Pokemon Proxy Service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    if http_client:
        await http_client.aclose()
    logger.info("Pokemon Proxy Service shut down") 