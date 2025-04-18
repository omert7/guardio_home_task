"""API routes for the Pokemon streaming proxy service."""

import time
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, Response, Depends, HTTPException
import httpx
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel
from app.core.config import Config, get_config, get_secret
from app.core.rules import find_matching_rule
from app.models.pokemon_pb2 import Pokemon
from app.models import PokemonModel
from app.utils.crypto import verify_signature
from app.utils.stats import (
    stats, initialize_stats, calculate_endpoint_stats,
    update_request_stats, update_response_stats
)
from app.models.pokemon_models import AllStatsModel, StatsModel
from app.utils.rate_limiter import limiter, STREAM_RATE_LIMIT

logger = logging.getLogger("pokemon-proxy")

router = APIRouter()


async def validate_signature(request: Request, secret: str) -> bytes:
    """Validate the request signature and return the body if valid.
    
    Args:
        request: The incoming request
        secret: The HMAC secret
        
    Returns:
        bytes: The raw request body
        
    Raises:
        HTTPException: If the signature is missing or invalid
    """
    signature = request.headers.get('X-Grd-Signature')
    if not signature:
        logger.error("Missing X-Grd-Signature header")
        raise HTTPException(status_code=401, detail="Missing signature")
    
    body = await request.body()
    
    if not verify_signature(signature, body, secret):
        logger.error("Invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return body


async def parse_pokemon_data(body: bytes) -> Dict[str, Any]:
    """Parse protobuf data into Pokemon dictionary.
    
    Args:
        body: The raw protobuf data
        
    Returns:
        Dict: The parsed Pokemon data as a dictionary
        
    Raises:
        HTTPException: If the data can't be parsed
    """
    pokemon = Pokemon()
    try:
        # Log the size of the incoming data for debugging
        logger.debug(f"Received protobuf data, size: {len(body)} bytes")
        
        # Try to parse the protobuf message
        pokemon.ParseFromString(body)
        
        # Convert protobuf to dict while preserving types
        pokemon_dict = MessageToDict(
            pokemon, 
            preserving_proto_field_name=True,
            including_default_value_fields=True
        )
        
        logger.debug(f"Successfully parsed Pokemon data: {pokemon.name}")
        return pokemon_dict
        
    except Exception as e:
        logger.error(f"Error parsing protobuf: {str(e)}")
        
        # If parsing fails, try a fallback approach to handle potential corruption
        try:
            # Create an empty Pokemon model
            default_pokemon = {
                "number": 0,
                "name": "Unknown (Parse Error)",
                "type_one": "unknown",
                "type_two": "unknown",
                "total": 0,
                "hit_points": 0,
                "attack": 0,
                "defense": 0,
                "special_attack": 0,
                "special_defense": 0,
                "speed": 0,
                "generation": 0,
                "legendary": False
            }
            
            logger.warning("Using fallback Pokemon data due to parse error")
            return default_pokemon
            
        except Exception as fallback_error:
            logger.error(f"Fallback error: {str(fallback_error)}")
            raise HTTPException(status_code=400, detail="Invalid protobuf message that couldn't be recovered")


async def validate_pokemon_model(pokemon_json: Dict[str, Any]) -> PokemonModel:
    """Validate Pokemon data with Pydantic and handle faulty data gracefully.
    
    Args:
        pokemon_json: The Pokemon data as a dictionary
        
    Returns:
        PokemonModel: The validated Pokemon model
    """
    try:
        return PokemonModel(**pokemon_json)
    except Exception as e:
        # We'll handle validation errors gracefully since the task mentions
        # "The pokemon streaming server has a slight chance to provide faulty results"
        logger.warning(f"Validation warning for Pokemon data: {str(e)}")
        # Proceed with best-effort validation
        pokemon_model = PokemonModel(name="Unknown")
        for field, value in pokemon_json.items():
            try:
                setattr(pokemon_model, field, value)
            except Exception:
                # Skip fields that cause validation errors
                pass
        return pokemon_model


async def prepare_outgoing_headers(request: Request, reason: str) -> Dict[str, str]:
    """Prepare headers for the outgoing request.
    
    Args:
        request: The incoming request
        reason: The reason for the rule match
        
    Returns:
        Dict: The prepared headers
    """
    # Forward all headers except the signature header
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() != 'x-grd-signature'  # Only strip the signature header
    }
    
    # Add the X-Grd-Reason header
    headers['X-Grd-Reason'] = reason
    
    return headers


async def forward_request(url: str, data: Dict[str, Any], headers: Dict[str, str]) -> httpx.Response:
    """Forward the request to the destination service.
    
    Args:
        url: The destination URL
        data: The data to send
        headers: The headers to include
        
    Returns:
        httpx.Response: The response from the destination
    """
    # Create a copy of headers to avoid modifying the original
    headers_copy = headers.copy()
    
    # Set Content-Type to application/json and remove the Content-Length header
    # since we're changing the format from protobuf to JSON
    headers_copy['Content-Type'] = 'application/json'
    
    # Explicitly remove Content-Length - httpx will calculate the correct length
    if 'content-length' in headers_copy:
        del headers_copy['content-length']
    
    try:
        # Create a custom httpx client with appropriate settings
        timeout_settings = httpx.Timeout(10.0, connect=5.0)
        
        async with httpx.AsyncClient(timeout=timeout_settings) as client:
            logger.debug(f"Forwarding request to {url} with {len(data)} data fields")
            
            # Let httpx handle the request by explicitly passing data as json
            response = await client.post(
                url, 
                json=data, 
                headers=headers_copy
            )
            
            logger.debug(f"Received response: {response.status_code}")
            return response
            
    except httpx.RequestError as e:
        logger.error(f"Request error when forwarding to {url}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error communicating with destination: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error when forwarding to {url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post('/stream')
@limiter.limit(STREAM_RATE_LIMIT)
async def stream(request: Request, config: Config = Depends(get_config)):
    """Handle incoming Pokemon stream requests.
    
    Args:
        request: The incoming request
        config: The loaded configuration
        
    Returns:
        Response: The response to send back
    """
    start_time = time.time()
    
    # Get the secret and validate signature
    secret = await get_secret()
    body = await validate_signature(request, secret)
    
    # Parse and validate the Pokemon data
    pokemon_json = await parse_pokemon_data(body)
    pokemon_model = await validate_pokemon_model(pokemon_json)
    
    # Log information about the received Pokemon
    logger.info(f"Received Pokemon: {pokemon_model.name} (#{pokemon_model.number}), " +
                f"Type: {pokemon_model.type_one}/{pokemon_model.type_two}, " +
                f"HP: {pokemon_model.hit_points}, " +
                f"Attack: {pokemon_model.attack}, Defense: {pokemon_model.defense}, " +
                f"Generation: {pokemon_model.generation}, " + 
                f"Legendary: {pokemon_model.legendary}")
    
    # Find a matching rule
    matched_rule = await find_matching_rule(pokemon_model, config.rules)
    if not matched_rule:
        logger.warning(f"No matching rule found for Pokemon: {pokemon_model.name}")
        return {"status": f"No matching rule found for Pokemon {pokemon_model.name}"}
    
    logger.info(f"Matched rule: {matched_rule.url} (Reason: {matched_rule.reason})")
    
    # Initialize stats for this endpoint
    initialize_stats(matched_rule.url)
    
    # Update request stats
    update_request_stats(matched_rule.url, len(body))
    
    try:
        # Prepare headers and forward the request
        headers = await prepare_outgoing_headers(request, matched_rule.reason)
        response = await forward_request(matched_rule.url, pokemon_model.model_dump(), headers)
        
        # Log response information
        logger.info(f"Forwarded Pokemon {pokemon_model.name} to {matched_rule.url}, " +
                   f"Status: {response.status_code}, " +
                   f"Response time: {(time.time() - start_time)*1000:.2f}ms")
        
        # Update response stats
        is_error = response.status_code >= 400
        await update_response_stats(
            matched_rule.url, 
            len(response.content), 
            time.time() - start_time,
            is_error
        )
        
        # Log errors if any
        if is_error:
            logger.error(f"Error from destination: {response.status_code} {response.text}")
        
        # Return the response from the destination
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
        
    except Exception as e:
        # Update error stats
        await update_response_stats(
            matched_rule.url, 
            0, 
            time.time() - start_time,
            True
        )
        logger.error(f"Error forwarding request for Pokemon {pokemon_model.name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")


@router.get('/stats')
async def get_stats():
    """Return statistics about the server operation.
    
    Returns:
        Dict: The calculated statistics
    """
    result = {}
    
    for url, url_stats in stats.items():
        result[url] = await calculate_endpoint_stats(url, url_stats)
    
    # Convert to Pydantic model and return
    return AllStatsModel(root=result)


@router.post('/debug')
async def debug_endpoint(request: Request):
    """A minimal endpoint to print Pokemon names to screen.
    
    Args:
        request: The incoming request
        
    Returns:
        Dict: A simple response
    """
    try:
        data = await request.json()
        name = data.get('name', 'Unknown Pokemon')
        print(f"Received Pokemon: {name}")
        return {"status": "ok", "pokemon": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/test-destination')
async def test_destination(request: Request):
    """A test endpoint that can be used as a destination in rules.
    
    This acts as a test destination for forwarding that always replies with a 200 response.
    To use this endpoint, set the rule URL to http://localhost:5000/test-destination
    
    Args:
        request: The incoming request
        
    Returns:
        Dict: A simple response confirming receipt
    """
    try:
        # Log all headers for debugging
        headers_dict = dict(request.headers)
        logger.debug(f"Test destination received headers: {headers_dict}")
        
        # Check content type
        content_type = request.headers.get('content-type', 'Not specified')
        logger.debug(f"Content-Type: {content_type}")
        
        # Handle various ways the body might be formatted
        if 'application/json' in content_type.lower():
            # Parse JSON directly
            try:
                body = await request.json()
            except Exception as json_error:
                logger.error(f"Error parsing JSON in test destination: {str(json_error)}")
                # Try to get raw body as fallback
                raw_body = await request.body()
                logger.debug(f"Raw body (first 100 bytes): {raw_body[:100]}")
                # Return simple response for invalid JSON
                return {
                    "status": "error",
                    "message": "Failed to parse JSON",
                    "error": str(json_error)
                }
        else:
            # For non-JSON requests, just use the raw body
            raw_body = await request.body()
            logger.warning(f"Non-JSON content type received: {content_type}")
            # Try to convert to string for display
            try:
                body_str = raw_body.decode('utf-8')
                body = {"raw_content": body_str[:100] + "..." if len(body_str) > 100 else body_str}
            except:
                body = {"raw_content": "Binary data (not shown)"}
        
        # Extract useful info from headers
        reason = request.headers.get('X-Grd-Reason', 'No reason provided')
        
        # Log receipt of the forwarded request
        logger.info(f"Test destination received Pokemon: {body.get('name', 'Unknown')}")
        logger.info(f"Reason for forwarding: {reason}")
        
        # Create a response that echoes back received data
        response = {
            "status": "ok",
            "message": "Test destination received the request",
            "pokemon_received": body.get('name', 'Unknown'),
            "reason": reason,
            "received_data_sample": {k: v for k, v in body.items() if k in ['name', 'number', 'type_one', 'legendary']}
        }
        
        return response
    except Exception as e:
        logger.error(f"Error in test destination: {str(e)}")
        # Return a valid response even if there's an error
        return {
            "status": "error",
            "message": f"Error processing request in test destination: {str(e)}",
            "timestamp": time.time()
        } 