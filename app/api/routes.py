"""API routes for the Pokemon streaming proxy service."""

import time
import logging
import asyncio
from typing import Dict, Any, List, Tuple

from fastapi import APIRouter, Request, Response, Depends, HTTPException
import httpx
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel
from app.core.config import Config, get_config, get_secret
from app.core.rules import find_matching_rule, find_all_matching_rules, Rule
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
        # Log the error
        logger.error(f"Error parsing protobuf: {str(e)}")
        
        # Log sample of the corrupted data for debugging
        try:
            sample = body[:100].hex() if len(body) > 0 else "empty"
            logger.error(f"Corrupted protobuf data sample (hex): {sample}")
        except Exception as sample_error:
            logger.error(f"Could not log data sample: {str(sample_error)}")
        
        # Return a clear error to the client
        raise HTTPException(
            status_code=400, 
            detail="Invalid or corrupted protobuf message"
        )


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


async def forward_to_multiple_destinations(destinations: List[Rule], 
                                         data: Dict[str, Any], 
                                         request_headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Forward the request to multiple destinations concurrently and gather all responses.
    
    Args:
        destinations: List of Rule objects with destination information
        data: The data to send to each destination
        request_headers: The base headers to include in each request
        
    Returns:
        List[Dict]: All responses with destination information
    """
    responses = []
    timeout_settings = httpx.Timeout(10.0, connect=5.0)
    
    # Prepare a list of destination information and tasks
    destination_tasks = []
    
    async with httpx.AsyncClient(timeout=timeout_settings) as client:
        # Create tasks for all destinations
        for rule in destinations:
            # Create headers with the specific reason for this rule
            headers = request_headers.copy()
            headers['X-Grd-Reason'] = rule.reason
            
            # Set Content-Type to application/json and remove Content-Length
            headers['Content-Type'] = 'application/json'
            if 'content-length' in headers:
                del headers['content-length']
                        
            # Create the task
            logger.debug(f"Preparing request to {rule.url} with reason: {rule.reason}")
            task = client.post(rule.url, json=data, headers=headers)
            destination_tasks.append((rule, task))
        
        # Execute all tasks concurrently with asyncio.gather
        if destination_tasks:
            # Split the rules and tasks
            rules, tasks = zip(*destination_tasks)
            
            # Wait for all tasks to complete (truly in parallel)
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process all results
            for rule, result in zip(rules, task_results):
                try:
                    if isinstance(result, Exception):
                        # Handle exceptions from gather
                        raise result
                    
                    # Get the response (result is now the httpx.Response)
                    response = result
                    
                    # Try to parse response content as JSON if possible
                    response_content = None
                    try:
                        response_content = response.json()
                    except Exception:
                        # If not JSON, try to decode as string if possible
                        try:
                            response_content = response.text
                        except Exception:
                            # If can't decode as string, use base64 encoding
                            import base64
                            response_content = {
                                "content_type": response.headers.get("content-type", "unknown"),
                                "encoded_content": base64.b64encode(response.content).decode('utf-8')
                            }
                    
                    # Make sure headers are serializable to JSON
                    safe_headers = {}
                    for key, value in response.headers.items():
                        # Convert header values to strings to ensure JSON serialization
                        safe_headers[key] = str(value)
                    
                    # Process the response
                    response_data = {
                        'url': rule.url,
                        'reason': rule.reason,
                        'status_code': response.status_code,
                        'content': response_content,
                        'headers': safe_headers
                    }
                    
                    # Update response stats
                    is_error = response.status_code >= 400
                    await update_response_stats(
                        rule.url, 
                        len(response.content), 
                        0,  # Time is tracked separately for each destination
                        is_error
                    )
                    
                    # Log errors if any
                    if is_error:
                        logger.error(f"Error from destination {rule.url}: {response.status_code} {response.text}")
                    
                    responses.append(response_data)
                    logger.debug(f"Received response from {rule.url}: status {response.status_code}")
                    
                except httpx.RequestError as e:
                    logger.error(f"Request error when forwarding to {rule.url}: {str(e)}")
                    # Include error information in the response
                    responses.append({
                        'url': rule.url,
                        'reason': rule.reason,
                        'status_code': 502,
                        'error': f"Error communicating with destination: {str(e)}"
                    })
                    # Update error stats
                    await update_response_stats(rule.url, 0, 0, True)
                    
                except Exception as e:
                    logger.error(f"Unexpected error when forwarding to {rule.url}: {str(e)}")
                    # Include error information in the response
                    responses.append({
                        'url': rule.url,
                        'reason': rule.reason,
                        'status_code': 500,
                        'error': f"Internal server error: {str(e)}"
                    })
                    # Update error stats
                    await update_response_stats(rule.url, 0, 0, True)
    
    return responses


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
    
    try:
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
        
        # Find all matching rules
        matched_rules = await find_all_matching_rules(pokemon_model, config.rules)
        if not matched_rules:
            logger.warning(f"No matching rules found for Pokemon: {pokemon_model.name}")
            return {"status": f"No matching rules found for Pokemon {pokemon_model.name}"}
        
        # Prepare base headers
        base_headers = await prepare_outgoing_headers(request, "Multiple Rules")
        
        # Update request stats for all destinations
        try:
            for rule in matched_rules:
                update_request_stats(rule.url, len(body))
        except Exception as stats_error:
            logger.error(f"Error updating request stats: {str(stats_error)}")
            # Continue processing even if stats update fails
        
        try:
            # Forward to all matching destinations
            all_responses = await forward_to_multiple_destinations(
                matched_rules, 
                pokemon_model.model_dump(), 
                base_headers
            )
            
            # Log overall response information
            logger.info(f"Forwarded Pokemon {pokemon_model.name} to {len(matched_rules)} destinations, " +
                      f"Total time: {(time.time() - start_time)*1000:.2f}ms")
            
            # Prepare the aggregate response
            aggregate_response = {
                "status": "success",
                "pokemon": pokemon_model.name,
                "matched_rules_count": len(matched_rules),
                "responses": all_responses
            }
            
            # Return the combined response
            return aggregate_response
            
        except Exception as e:
            # Update error stats for all destinations
            try:
                for rule in matched_rules:
                    await update_response_stats(rule.url, 0, time.time() - start_time, True)
            except Exception as stats_error:
                logger.error(f"Error updating error stats: {str(stats_error)}")
                
            logger.error(f"Error forwarding requests for Pokemon {pokemon_model.name}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error forwarding requests: {str(e)}")
    
    except HTTPException:
        # Re-raise HTTPExceptions (like 401 for invalid signature)
        raise
    
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error processing stream request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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


@router.post('/test-destination-2')
async def test_destination_2(request: Request):
    """A second test endpoint with different response format.
    
    This endpoint is used to verify multi-rule forwarding works correctly.
    To use this endpoint, set the rule URL to http://localhost:5000/test-destination-2
    
    Args:
        request: The incoming request
        
    Returns:
        Dict: A response with a different format from the first test endpoint
    """
    try:
        # Log all headers for debugging
        headers_dict = dict(request.headers)
        logger.debug(f"Test destination 2 received headers: {headers_dict}")
        
        # Get the reason from headers
        reason = request.headers.get('X-Grd-Reason', 'No reason provided')
        
        # Parse the request body
        try:
            body = await request.json()
        except Exception:
            body = {"error": "Could not parse JSON body"}
        
        # Extract Pokemon info
        pokemon_name = body.get('name', 'Unknown')
        pokemon_type = body.get('type_one', 'Unknown')
        
        logger.info(f"Test destination 2 received Pokemon: {pokemon_name} (Type: {pokemon_type})")
        logger.info(f"Reason for forwarding to endpoint 2: {reason}")
        
        # Return a distinctly different response format so we can tell endpoints apart
        return {
            "endpoint": "test-destination-2",
            "status": "received",
            "pokemon_details": {
                "name": pokemon_name,
                "primary_type": pokemon_type,
                "is_legendary": body.get('legendary', False)
            },
            "forwarding_reason": reason,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error in test destination 2: {str(e)}")
        return {
            "endpoint": "test-destination-2",
            "status": "error",
            "error_details": str(e),
            "timestamp": time.time()
        }
