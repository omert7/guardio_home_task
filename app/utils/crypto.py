"""Cryptographic utilities for signature verification."""

import base64
import hmac
import hashlib
import logging

logger = logging.getLogger("pokemon-proxy")

def verify_signature(signature: str, body: bytes, secret: str) -> bool:
    """Verify the HMAC-SHA256 signature of the request.
    
    Args:
        signature: The signature from the X-Grd-Signature header
        body: The raw request body
        secret: Base64-encoded HMAC secret
        
    Returns:
        bool: True if the signature is valid, False otherwise
    """
    try:
        # Decode the base64 secret
        decoded_secret = base64.b64decode(secret)
        
        # Compute the HMAC-SHA256 hash
        computed_hash = hmac.new(
            decoded_secret, 
            body, 
            hashlib.sha256
        ).hexdigest()
        
        # Compare the computed hash with the provided signature
        return hmac.compare_digest(computed_hash, signature)
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False 