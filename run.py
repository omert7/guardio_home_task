#!/usr/bin/env python3
"""Entry point for the Pokemon streaming proxy service."""

import asyncio
import logging
import os
import sys
import uvicorn

from app.core.config import Config, validate_config_exists
from validate_config import validate_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("pokemon-proxy")


async def initialize_app():
    """Initialize the application and validate the configuration."""
    try:
        config_path = await validate_config_exists()
        
        # First validate config format according to task requirements
        logger.info(f"Validating configuration format: {config_path}")
        valid, errors = validate_config(config_path)
        
        if not valid:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            raise ValueError("Invalid configuration format")
        
        # Then load config with Pydantic model
        Config(config_path)  # Validate by trying to load it
        logger.info(f"Configuration validated and loaded successfully: {config_path}")
        
        # Print a summary of the rules
        with open(config_path, 'r') as f:
            import json
            config = json.load(f)
        
        logger.info(f"Found {len(config['rules'])} rules:")
        for i, rule in enumerate(config['rules']):
            match_count = len(rule['match'])
            match_desc = f"{match_count} conditions" if match_count > 0 else "ALL Pokemon (no conditions)"
            logger.info(f"  {i+1}. {rule['reason']} -> {rule['url']} ({match_desc})")
            # Log details of conditions
            if match_count > 0:
                for condition in rule['match']:
                    logger.info(f"     - {condition}")
        
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        raise


def main():
    """Run the application."""
    # Initialize the app
    try:
        asyncio.run(initialize_app())
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        sys.exit(1)
        
    # Start the server
    logger.info("Starting Pokemon proxy server")
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 5000)),
        log_level="info"
    )


if __name__ == "__main__":
    main() 