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
    return {
        'request_count': url_stats['request_count'],
        'error_rate': (url_stats['error_count'] / url_stats['request_count']) * 100 if url_stats['request_count'] > 0 else 0,
        'bytes_in': url_stats['bytes_in'],
        'bytes_out': url_stats['bytes_out'],
        'avg_response_time_ms': sum(url_stats['response_times']) / len(url_stats['response_times']) * 1000 if url_stats['response_times'] else 0
#        'uptime_seconds': (datetime.now() - url_stats['start_time']).total_seconds()
    }

def update_request_stats(url: str, body_length: int) -> None:
    """Update request statistics.
    
    Args:
        url: The endpoint URL
        body_length: Length of the request body in bytes
    """
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
    stats[url]['bytes_out'] += response_content_length
    stats[url]['response_times'].append(response_time)
    
    if is_error:
        stats[url]['error_count'] += 1 