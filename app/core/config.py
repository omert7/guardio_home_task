"""Configuration handling for the Pokemon streaming proxy service."""

import os
import json
import logging
from typing import Optional

from fastapi import HTTPException

from app.models import ConfigModel

logger = logging.getLogger("pokemon-proxy")

class Config:
    """Configuration handler for the Pokemon proxy service."""
    
    def __init__(self, config_path: str):
        """Initialize configuration from a file.
        
        Args:
            config_path: Path to the configuration file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file isn't valid JSON
        """
        self.rules = []
        self.load_config(config_path)
        
    def load_config(self, config_path: str):
        """Load and validate configuration from a file.
        
        Args:
            config_path: Path to the configuration file
        """
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            # Validate using Pydantic
            config = ConfigModel(**config_data)
            self.rules = config.rules
            logger.info(f"Loaded {len(self.rules)} rules from config")


async def get_config() -> Config:
    """Dependency to get configuration.
    
    Returns:
        Config: The loaded configuration
        
    Raises:
        HTTPException: If the configuration can't be loaded
    """
    config_path = os.environ.get('POKEPROXY_CONFIG')
    
    if not config_path:
        raise HTTPException(status_code=500, detail="POKEPROXY_CONFIG environment variable not set")
    
    try:
        return Config(config_path)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading configuration")


async def get_secret() -> str:
    """Get the HMAC secret from environment variables.
    
    Returns:
        str: The secret
        
    Raises:
        HTTPException: If the secret is not set
    """
    secret = os.environ.get('ENC_SECRET')
    if not secret:
        logger.error("ENC_SECRET environment variable not set")
        raise HTTPException(status_code=500, detail="Server configuration error")
    return secret


async def validate_config_exists() -> str:
    """Validate that the configuration path exists.
    
    Returns:
        str: The configuration path
        
    Raises:
        ValueError: If the configuration path is not set
    """
    config_path = os.environ.get('POKEPROXY_CONFIG')
    if not config_path:
        error_msg = "POKEPROXY_CONFIG environment variable not set"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return config_path 