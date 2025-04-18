"""Statistics tracking utilities."""

from datetime import datetime
from typing import Dict, Any

# Global stats storage
stats = {}

def initialize_stats(url: str) -> None:
    """Initialize stats for a new endpoint if needed.
    
    Args:
        url: The endpoint URL to initialize stats for
    """
    if url not in stats:
        stats[url] = {
            'request_count': 0,
            'error_count': 0,
            'bytes_in': 0,
            'bytes_out': 0,
            'response_times': [],
            'start_time': datetime.now()
        }

async def calculate_endpoint_stats(url: str, url_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate statistics for a specific endpoint.
    
    Args:
        url: The endpoint URL
        url_stats: Raw stats data for the endpoint
        
    Returns:
        Dict: Calculated statistics
    """
    request_count = url_stats.get('request_count', 0)
    error_count = url_stats.get('error_count', 0)
    response_times = url_stats.get('response_times', [])
    
    # Calculate metrics safely
    error_rate = (error_count / request_count) * 100 if request_count > 0 else 0
    avg_response_time = sum(response_times) / len(response_times) * 1000 if response_times else 0
    
    return {
        'request_count': request_count,
        'error_rate': error_rate,
        'bytes_in': url_stats.get('bytes_in', 0),
        'bytes_out': url_stats.get('bytes_out', 0),
        'avg_response_time_ms': avg_response_time
    }

def update_request_stats(url: str, body_length: int) -> None:
    """Update request statistics.
    
    Args:
        url: The endpoint URL
        body_length: Length of the request body in bytes
    """
    # Initialize stats if they don't exist yet
    initialize_stats(url)
    
    stats[url]['request_count'] += 1
    stats[url]['bytes_in'] += body_length

async def update_response_stats(url: str, response_content_length: int, response_time: float, is_error: bool = False) -> None:
    """Update response statistics.
    
    Args:
        url: The endpoint URL
        response_content_length: Length of the response content in bytes
        response_time: Response time in seconds
        is_error: Whether the response is an error
    """
    # Initialize stats if they don't exist yet
    initialize_stats(url)
    
    stats[url]['bytes_out'] += response_content_length
    stats[url]['response_times'].append(response_time)
    
    if is_error:
        stats[url]['error_count'] += 1 