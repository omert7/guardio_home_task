#!/usr/bin/env python3
"""Tool for testing the Pokemon streaming proxy with faulty data."""

import os
import base64
import hmac
import hashlib
import argparse
import json
import random
import httpx

from app.models.pokemon_pb2 import Pokemon

def generate_hmac(message: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for the message."""
    # Decode the base64 secret
    decoded_secret = base64.b64decode(secret)
    
    # Compute the HMAC-SHA256 hash
    digest = hmac.new(
        decoded_secret, 
        message, 
        hashlib.sha256
    ).hexdigest()
    
    return digest

def create_faulty_pokemon():
    """Create various faulty Pokemon messages for testing edge cases."""
    test_cases = []
    
    # Case 1: Pokemon with extremely large values
    pokemon1 = Pokemon()
    pokemon1.number = 2**63 - 1  # Max uint64 value
    pokemon1.name = "MaxValuePokemon"
    pokemon1.attack = 2**63 - 1
    pokemon1.defense = 2**63 - 1
    pokemon1.hit_points = 2**63 - 1
    pokemon1.special_attack = 2**63 - 1
    pokemon1.special_defense = 2**63 - 1
    pokemon1.speed = 2**63 - 1
    test_cases.append(("Extreme values", pokemon1))
    
    # Case 2: Pokemon with empty fields
    pokemon2 = Pokemon()
    pokemon2.number = 0
    test_cases.append(("Empty fields", pokemon2))
    
    # Case 3: Pokemon with very long string values
    pokemon3 = Pokemon()
    pokemon3.number = 3
    pokemon3.name = "A" * 10000
    pokemon3.type_one = "B" * 10000
    pokemon3.type_two = "C" * 10000
    test_cases.append(("Very long strings", pokemon3))
    
    # Case 4: Pokemon with special characters
    pokemon4 = Pokemon()
    pokemon4.number = 4
    pokemon4.name = "Pika<script>alert('XSS')</script>chu"
    pokemon4.type_one = "Electric'; DROP TABLE pokemon;--"
    pokemon4.type_two = "<img src=x onerror=alert('XSS')>"
    test_cases.append(("Special characters (security test)", pokemon4))
    
    # Case 5: Pokemon with invalid UTF-8 sequences
    pokemon5 = Pokemon()
    pokemon5.number = 5
    pokemon5.name = "Invalid UTF-8: \uD800"  # Surrogate code point
    test_cases.append(("Invalid UTF-8", pokemon5))
    
    return test_cases

def send_pokemon(url: str, pokemon: Pokemon, secret: str, corrupt_signature=False):
    """Send a Pokemon to the proxy server."""
    # Serialize the Pokemon to bytes
    pokemon_bytes = pokemon.SerializeToString()
    
    # Generate the HMAC signature
    signature = generate_hmac(pokemon_bytes, secret)
    
    # Optionally corrupt the signature
    if corrupt_signature:
        signature = signature[:-1] + ('1' if signature[-1] != '1' else '2')
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/octet-stream',
        'X-Grd-Signature': signature
    }
    
    # Send the request
    try:
        response = httpx.post(
            url,
            content=pokemon_bytes,
            headers=headers,
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response: {response.text[:100]} (truncated)")
        
        return response.status_code
    except Exception as e:
        print(f"Error: {str(e)}")
        return 0

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Send faulty Pokemon data to test edge cases')
    parser.add_argument('--url', default='http://localhost:5000/stream', help='URL of the proxy server')
    parser.add_argument('--secret', help='Base64 encoded HMAC secret')
    parser.add_argument('--corrupt-signatures', action='store_true', help='Also test with corrupted signatures')
    args = parser.parse_args()
    
    if not args.secret:
        print("Error: --secret is required")
        return
    
    # Create faulty Pokemon test cases
    test_cases = create_faulty_pokemon()
    
    # Send each test case
    for description, pokemon in test_cases:
        print(f"\n=== Testing: {description} ===")
        print("With valid signature:")
        send_pokemon(args.url, pokemon, args.secret)
        
        if args.corrupt_signatures:
            print("\nWith corrupted signature:")
            send_pokemon(args.url, pokemon, args.secret, corrupt_signature=True)

if __name__ == '__main__':
    main()