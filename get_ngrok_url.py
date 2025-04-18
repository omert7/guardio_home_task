#!/usr/bin/env python3
"""Script to fetch and display the ngrok public URL."""

import requests
import json
import time
import sys
import os

def get_ngrok_url():
    """Get the public URL from the ngrok API."""
    try:
        # Wait for ngrok to start
        print("Waiting for ngrok to initialize...")
        time.sleep(5)
        
        # Get tunnels from ngrok API
        # Use ngrok container name when in Docker network
        ngrok_host = os.environ.get("NGROK_HOST", "ngrok")
        ngrok_port = os.environ.get("NGROK_PORT", "4040")
        ngrok_api_url = f"http://{ngrok_host}:{ngrok_port}/api/tunnels"
        
        print(f"Connecting to ngrok API at {ngrok_api_url}")
        response = requests.get(ngrok_api_url)
        data = response.json()
        
        # Find https tunnel
        for tunnel in data["tunnels"]:
            if tunnel["proto"] == "https":
                url = tunnel["public_url"]
                return url
                
        # If no https tunnel is found
        if data["tunnels"]:
            return data["tunnels"][0]["public_url"]
        else:
            return None
    except Exception as e:
        print(f"Error getting ngrok URL: {e}")
        return None

def print_guardio_request(url):
    """Print the Guardio stream request with the ngrok URL."""
    stream_url = f"{url}/stream"
    # Get secret from environment or use default
    enc_secret = os.environ.get("ENC_SECRET", "6Jf1bBHYv7QNSWJU8+xrDvkKLBrtbmgcE1ryqoR7mUU=")
    
    request = {
        "url": stream_url,
        "email": "test@guard.io",
        "enc_secret": enc_secret
    }
    
    print("\n" + "="*50)
    print("GUARDIO STREAM REQUEST:")
    print("="*50)
    print("POST https://hiring.external.guardio.dev/be/stream_start")
    print("Headers: Content-Type: application/json")
    print("Body:")
    print(json.dumps(request, indent=2))
    print("="*50)
    
    print("\nCURL Command:")
    print(f"""curl -X POST https://hiring.external.guardio.dev/be/stream_start \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(request)}'""")
    print("="*50)

if __name__ == "__main__":
    print("="*50)
    print("NGROK URL FINDER")
    print("="*50)
    
    # Try multiple times as ngrok might take time to start
    max_attempts = 12  # 12 attempts x 5 seconds = 1 minute max wait
    for i in range(max_attempts):
        print(f"Attempt {i+1}/{max_attempts}...")
        url = get_ngrok_url()
        if url:
            print(f"\n🚀 SUCCESS: Ngrok URL found!")
            print(f"👉 {url}")
            print_guardio_request(url)
            sys.exit(0)
        time.sleep(5)
    
    print("\n❌ ERROR: Failed to get ngrok URL after multiple attempts")
    print("- Check if ngrok container is running")
    print("- Verify NGROK_AUTHTOKEN is correctly set in .env")
    print("- Inspect logs with: docker logs ngrok")
    sys.exit(1) 