#!/usr/bin/env python3
"""Test client for the Pokemon streaming proxy service."""

import os
import base64
import hmac
import hashlib
import argparse
import json
import asyncio
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

def create_pokemon(
    number=1, 
    name="Bulbasaur", 
    type_one="Grass", 
    type_two="Poison",
    total=318,
    hit_points=45,
    attack=49,
    defense=49,
    special_attack=65,
    special_defense=65,
    speed=45,
    generation=1,
    legendary=False
):
    """Create a Pokemon message."""
    pokemon = Pokemon()
    pokemon.number = number
    pokemon.name = name
    pokemon.type_one = type_one
    pokemon.type_two = type_two
    pokemon.total = total
    pokemon.hit_points = hit_points
    pokemon.attack = attack
    pokemon.defense = defense
    pokemon.special_attack = special_attack
    pokemon.special_defense = special_defense
    pokemon.speed = speed
    pokemon.generation = generation
    pokemon.legendary = legendary
    
    return pokemon

def send_pokemon(url: str, pokemon: Pokemon, secret: str):
    """Send a Pokemon to the proxy server."""
    # Serialize the Pokemon to bytes
    pokemon_bytes = pokemon.SerializeToString()
    
    # Generate the HMAC signature
    signature = generate_hmac(pokemon_bytes, secret)
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/octet-stream',
        'X-Grd-Signature': signature
    }
    
    # Send the request
    response = httpx.post(
        url,
        content=pokemon_bytes,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {response.json()}")
    except:
        print(f"Response: {response.text}")

async def send_pokemon_async(url: str, pokemon: Pokemon, secret: str):
    """Send a Pokemon to the proxy server asynchronously."""
    # Serialize the Pokemon to bytes
    pokemon_bytes = pokemon.SerializeToString()
    
    # Generate the HMAC signature
    signature = generate_hmac(pokemon_bytes, secret)
    
    # Prepare headers
    headers = {
        'Content-Type': 'application/octet-stream',
        'X-Grd-Signature': signature
    }
    
    # Send the request asynchronously
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            content=pokemon_bytes,
            headers=headers
        )
    
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {response.json()}")
    except:
        print(f"Response: {response.text}")
    
    return response

async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(description='Test client for Pokemon proxy server')
    parser.add_argument('--url', default='http://localhost:5000/stream', help='URL of the proxy server')
    parser.add_argument('--secret', help='Base64 encoded HMAC secret')
    parser.add_argument('--pokemon', help='JSON file with Pokemon data')
    parser.add_argument('--stats', action='store_true', help='Fetch stats from the server')
    parser.add_argument('--concurrent', type=int, default=1, help='Number of concurrent requests to send')
    args = parser.parse_args()
    
    if args.stats:
        # Get the stats
        async with httpx.AsyncClient() as client:
            response = await client.get(args.url.replace('/stream', '/stats'))
            print(json.dumps(response.json(), indent=2))
        return
    
    if not args.secret:
        print("Error: --secret is required")
        return
    
    if args.pokemon:
        # Load Pokemon from JSON file
        with open(args.pokemon, 'r') as f:
            pokemon_data = json.load(f)
            pokemon = create_pokemon(**pokemon_data)
    else:
        # Create a default Pokemon
        pokemon = create_pokemon()
    
    # Send the Pokemon with specified concurrency
    if args.concurrent > 1:
        tasks = []
        for i in range(args.concurrent):
            # Create a slightly modified Pokemon for each request
            p = create_pokemon(
                number=i+1,
                name=f"{pokemon.name}_{i+1}",
                hit_points=pokemon.hit_points + i
            )
            tasks.append(send_pokemon_async(args.url, p, args.secret))
        
        print(f"Sending {args.concurrent} concurrent requests...")
        await asyncio.gather(*tasks)
    else:
        # Send a single Pokemon
        await send_pokemon_async(args.url, pokemon, args.secret)

def main():
    """Main function."""
    asyncio.run(main_async())

if __name__ == '__main__':
    main() 