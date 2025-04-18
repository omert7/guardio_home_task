# Pokemon Streaming Proxy Service

A proxy service that integrates with Guardio's Pokemon stream API, normalizes it, and routes it to downstream services based on a configuration file.

## Features

- Built with FastAPI for high performance async processing
- Pydantic models for automatic data validation
- Validates incoming Pokemon data against HMAC-SHA256 signatures
- Routes Pokemon to downstream services based on matching rules
- Converts protobuf messages to JSON format
- Handles error cases gracefully
- Provides statistics endpoint for monitoring
- Robust error handling for faulty data
- Concurrent request handling for high throughput
- Docker support for easy deployment
- Automatic API documentation with Swagger UI
- Dynamic Protobuf generation
- Graceful fallback for corrupted messages
- Proper header management in forwarding requests

## Project Structure

```
pokemon-proxy/
│
├── app/                    # Application package
│   ├── api/                # API endpoints
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI application
│   │   └── routes.py       # API routes
│   │
│   ├── core/               # Core business logic
│   │   ├── __init__.py
│   │   ├── config.py       # Configuration handling
│   │   └── rules.py        # Rule matching logic
│   │
│   ├── models/             # Data models
│   │   ├── __init__.py
│   │   └── pokemon_models.py # Pydantic models
│   │
│   ├── utils/              # Utility functions
│   │   ├── __init__.py
│   │   ├── crypto.py       # Cryptographic utilities
│   │   ├── rate_limiter.py # Rate limiting functionality
│   │   └── stats.py        # Statistics tracking
│   │
│   └── __init__.py
│
├── tests/                  # Test suite
│
├── .env                    # Environment variables (not in git)
├── config.json             # Sample configuration
├── pokemon.proto           # Protobuf schema definition
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose configuration
├── get_ngrok_url.py        # Helper script for ngrok
├── ngrok-config.yml        # Configuration for ngrok
├── run.py                  # Entry point script
├── start.bat               # Windows startup script
├── start.sh                # Linux/Mac startup script
├── validate_config.py      # Configuration validator
├── sample_pokemon.json     # Sample Pokemon data
├── faulty_pokemon.py       # Tool for testing error handling
├── test_client.py          # Test client for the service
└── requirements.txt        # Python dependencies
```

Note: The `pokemon_pb2.py` file is not included in the repository but will be generated at runtime when you run the protoc command or build the Docker image.

## Setup

### Local Development

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Install the Protocol Buffers compiler (protoc) and generate the Python code:
```
# Install protoc
# On Ubuntu/Debian:
apt-get install protobuf-compiler

# On macOS:
brew install protobuf

# On Windows:
# Download from https://github.com/protocolbuffers/protobuf/releases

# Generate the Python code
mkdir -p app/models
protoc --python_out=app/models pokemon.proto
```

3. Create a `.env` file in the project root:
```
POKEPROXY_CONFIG=config.json
ENC_SECRET=your_base64_encoded_secret
```

4. Run the server:
```
python run.py
```

Alternatively, you can use the convenience scripts:
- On Windows: `start.bat`
- On Linux/macOS: `./start.sh`

These scripts handle environment setup and start the server.

5. **Important**: Make your service publicly accessible

For the Guardio Pokemon stream to send data to your service, it needs to be publicly accessible from the internet. You have several options:

- **Use ngrok** (easiest):
  ```
  ngrok http 5000
  ```
  Then use the ngrok URL for registering with Guardio's service

- **Configure port forwarding** on your router (if you have a public IP)

- **Deploy to a cloud service** like AWS, GCP, Azure, or Heroku

Without making your service publicly accessible, the Guardio Pokemon stream won't be able to send data to your service.

### Docker Deployment

The simplest way to deploy the service is using Docker Compose:

```bash
docker-compose up
```

This will:
1. Build the Docker image with all dependencies
2. Generate the Protobuf code during the build
3. Validate your configuration file against the format requirements
4. Start the Pokemon Proxy service
5. Start ngrok to make the service publicly accessible (if configured)

The Docker deployment includes several safety features:
- Config validation at build time to prevent deploying with invalid configuration
- Config validation at container startup to catch any mounted volume changes
- Health checks that verify the service is healthy and configuration remains valid

If the configuration validation fails, the container will not start properly and will show detailed error messages to help you fix the issues.

### Environment Variables

The service uses the following environment variables:

- `POKEPROXY_CONFIG`: Path to the configuration file (required)
- `ENC_SECRET`: Base64-encoded HMAC secret for signature validation (required)
- `PORT`: Port to run the service on (default: 5000)
- `NGROK_AUTHTOKEN`: Authentication token for ngrok (required for ngrok integration)
- `DEFAULT_RATE_LIMIT`: Default rate limit for all endpoints (default: "120/minute")
- `STREAM_RATE_LIMIT`: Specific rate limit for the /stream endpoint (default: "100/minute")
- `RATE_LIMIT_STORAGE`: Optional Redis URL for distributed rate limiting (e.g., "redis://redis:6379/0")

Rate limits are specified in the format "number/period" where period can be "second", "minute", "hour", or "day".

## Running with ngrok for Public Access

For the Guardio Pokemon stream to send data to your service, it needs to be publicly accessible. The project includes ngrok integration through Docker to easily make your service available on the internet.

### Prerequisites

1. Get an ngrok authentication token from https://dashboard.ngrok.com/get-started/your-authtoken
2. Add the token to your `.env` file:
   ```
   NGROK_AUTHTOKEN=your_ngrok_auth_token
   ```

### Starting with Docker Compose

Simply run Docker Compose to start all services (Pokemon proxy, ngrok, and the URL display helper):

```bash
docker-compose up
```

This will:
1. Start the Pokemon Proxy service
2. Start ngrok connected to the proxy
3. Run a helper container that displays the public ngrok URL
4. Display the complete request to send to Guardio's API

The ngrok URL will be displayed in the console output. You can use this URL to register with Guardio's streaming service.

### Accessing Services

- Pokemon Proxy: http://localhost:5000
- ngrok Web Interface: http://localhost:4040 (useful for inspecting requests)

### Starting the Guardio Stream

With your URL from ngrok, send a POST request to Guardio's service:

```bash
curl -X POST https://hiring.external.guardio.dev/be/stream_start \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-ngrok-url.ngrok.io/stream",
    "email": "test@guard.io",
    "enc_secret": "your_base64_encoded_secret"
  }'
```

Replace `your_base64_encoded_secret` with the same value from your `.env` file.

## API Documentation

The FastAPI implementation includes automatic API documentation:
- Swagger UI: `http://localhost:5000/docs`
- ReDoc: `http://localhost:5000/redoc`

## Endpoints

### `/stream` - Main Proxy Endpoint

Receives protobuf-encoded Pokemon data, validates the signature, checks against rules, converts to JSON, and forwards to matching destinations.

- Method: `POST`
- Headers:
  - `X-Grd-Signature`: HMAC-SHA256 signature of the request body
- Body: Protobuf-encoded Pokemon data
- Response: JSON object containing:
  - `status`: Status of the operation ("success" or error message)
  - `pokemon`: Name of the processed Pokemon
  - `matched_rules_count`: Number of matching rules found
  - `responses`: Array of responses from all matching destinations, each containing:
    - `url`: The destination URL
    - `reason`: The reason for matching from the rule
    - `status_code`: HTTP status code from the destination
    - `content`: Content of the response (parsed as JSON if possible, otherwise text or base64 encoded)
    - `headers`: Headers from the destination response

Note: The service will concurrently forward requests to all matching destinations and gather all responses into a single aggregate response.

### `/stats` - Statistics Endpoint

Returns statistics about the forwarded requests.

- Method: `GET`
- Response: JSON object with statistics for each endpoint:
  - `request_count`: Number of requests processed
  - `error_rate`: Percentage of requests that resulted in errors
  - `bytes_in`: Total bytes received
  - `bytes_out`: Total bytes sent
  - `avg_response_time_ms`: Average response time in milliseconds
  - `uptime_seconds`: Service uptime in seconds

### `/health` - Health Check Endpoint

Simple health check for Docker healthchecks and monitoring.

- Method: `GET`
- Response: `{"status": "healthy"}`

### `/debug` - Debug Endpoint

Simple debug endpoint for testing.

- Method: `POST`
- Body: `{"name": "Pokemon Name"}`
- Response: `{"status": "ok", "pokemon": "Pokemon Name"}`

### `/test-destination` - Test Destination Endpoint

A built-in endpoint that can be used as a destination in your routing rules for testing.

- Method: `POST`
- Body: Any JSON data (typically Pokemon data)
- Response: Response confirming receipt of the data
- Note: This endpoint is pre-configured in the sample `config.json` file

### `/test-destination-2` - Second Test Destination

A second test endpoint with a different response format to verify multi-rule forwarding works correctly.

- Method: `POST`
- Body: Any JSON data (typically Pokemon data)
- Response: Different format response with Pokemon details
- Note: Used together with the first test endpoint to demonstrate multi-rule matching

## Multi-Rule Matching and Parallel Processing

The service is designed to match Pokemon against all rules in the configuration, not just the first matching rule. When multiple rules match:

1. The requests to all matching destinations are sent **concurrently** (in parallel)
2. All responses are gathered and returned in a combined response object
3. The service can handle different response formats from different destinations
4. If any destination returns an error, the service continues processing other destinations

This enables advanced routing scenarios where the same Pokemon can be sent to multiple specialized services based on different attributes.

### Rate Limiting with Multi-Rule Forwarding

When using multi-rule forwarding, the rate limiting system has been optimized to:

1. Count the incoming Pokemon request as a single request, regardless of how many rules it matches
2. Use a fault-tolerant client identification system to prevent rate limiting errors
3. Handle concurrent requests efficiently without blocking
4. Provide detailed error messages when rate limits are exceeded

Rate limits can be configured via environment variables:
- `STREAM_RATE_LIMIT`: The rate limit for the `/stream` endpoint (default: "100/minute")
- `DEFAULT_RATE_LIMIT`: The default rate limit for all other endpoints (default: "120/minute")


## Configuration

The service is configured using a JSON file specified by the `POKEPROXY_CONFIG` environment variable. Example:

```json
{
  "rules": [
    {
      "url": "http://my-pokemon-service.com/endpoint",
      "reason": "Legendary Pokemon",
      "match": [
        "legendary==true",
        "generation<3"
      ]
    },
    {
      "url": "http://debug-service/pokemon",
      "reason": "Debug endpoint",
      "match": []
    }
  ]
}
```

### Rule Structure

- `url`: The destination URL to forward matching Pokemon to
- `reason`: Human-readable reason for the match (included in the `X-Grd-Reason` header)
- `match`: List of conditions that all must be true for the rule to match
  - Format: `field<operator>value`
  - Operators: `==`, `!=`, `>`, `<`
  - Empty list matches everything

### Configuration Validation

The service includes built-in configuration validation to ensure your `config.json` follows the correct format. This validation happens:

1. **At startup**: The application validates the configuration when it starts up
2. **In Docker**: The Docker container validates the configuration before starting the service
3. **Manually**: You can manually validate your configuration using the included script:
   ```bash
   python validate_config.py
   ```

The validation checks for:

- Correct JSON structure with a "rules" array
- Required fields ("url", "reason", "match") for each rule
- Valid match rule format (`field operator value`)
- Valid operators (`==`, `!=`, `>`, `<`)
- No invalid combinations or syntax errors

If validation fails, you'll see detailed error messages explaining what needs to be fixed.

### Sample Files

The repository includes several sample files to help you get started:

1. **sample_pokemon.json**: Contains a sample Pokemon object that can be used with the test client
2. **config.json**: A sample configuration file with rules that forward to the built-in test destination
3. **faulty_pokemon.py**: A script that generates faulty Pokemon data to test error handling

These files can be used with the test client for local development:

```bash
# Test with sample Pokemon
python test_client.py --secret "your_base64_encoded_secret" --pokemon sample_pokemon.json
```

## Error Handling and Robustness

The service includes several features to handle errors gracefully:

1. **Robust Protobuf Handling**: If a protobuf message can't be parsed, the service returns a clear error response with HTTP 400 status code, including debugging information in the logs
2. **Header Management**: Problematic headers are removed when forwarding requests to avoid issues with Content-Length
3. **Validation with Grace**: Fields that fail validation are logged but don't cause the entire request to fail
4. **Rate Limiting**: Automatic rate limiting through FastAPI/Starlette to prevent abuse
5. **Timeouts**: Connection timeouts to prevent hanging connections
6. **Detailed Logging**: Comprehensive logging for debugging and monitoring
7. **Concurrent Error Handling**: When forwarding to multiple destinations, errors from one destination don't prevent forwarding to others

## Testing

Run tests with pytest:

```
pytest tests/
```

You can also use the provided tools to test manually:

1. Test with a sample Pokemon:
```
python test_client.py --secret "your_base64_encoded_secret" --pokemon sample_pokemon.json
```

2. Check server stats:
```
python test_client.py --stats
```

3. Test with faulty Pokemon data:
```
python faulty_pokemon.py --secret "your_base64_encoded_secret"
```

4. Test concurrent requests:
```
python test_client.py --secret "your_base64_encoded_secret" --concurrent 10
```

## Architecture
```
┌───────────────┐       ┌─────────────────┐       ┌────────────────┐
│ Guardio       │       │ Pokemon Proxy   │       │ Downstream     │
│ Pokemon Stream│──────▶│ Service         │──────▶│ Services       │
└───────────────┘       └─────────────────┘       └────────────────┘
                        │                 │
                        │   Rule-Based    │
                        │   Routing       │
                        └─────────────────┘
```

## Performance and Reliability Enhancements

1. **Asynchronous Processing**: Uses async/await for handling requests, which allows the server to process multiple requests concurrently without blocking.

2. **Data Validation**: Uses Pydantic models for automatic validation, type conversion, and error handling.

3. **Dynamic Protobuf Generation**: Generates protobuf code during Docker build for better compatibility.

4. **Header Management**: Careful handling of HTTP headers to avoid common issues like Content-Length mismatches.

5. **Proper Error Handling**: Clear error responses with appropriate HTTP status codes for invalid or corrupted data.

6. **Docker Health Checks**: Container health monitoring to ensure service availability.

7. **Isolated Services**: Each component runs in its own container for better isolation and scalability.

8. **Automatic Documentation**: Generates OpenAPI documentation automatically.

9. **Configurable Rate Limiting**: Prevents abuse and ensures service stability by limiting clients to a configurable number of requests per time period. By default, the /stream endpoint is limited to 100 requests per minute per IP address. These limits can be adjusted via environment variables.

## Troubleshooting

### Common Issues

1. **Protobuf Generation Errors**: If you encounter protobuf-related errors, make sure the protobuf compiler (protoc) version is compatible with the Python protobuf package version.

2. **Content-Length Issues**: If you see "Too much data for declared Content-Length" errors, this is now handled automatically by the header management in the forwarding logic.

3. **Configuration Validation Errors**: If the service fails to start due to configuration validation errors:
   - Check the format of your `config.json` file
   - Ensure all rules have the required `url`, `reason`, and `match` fields
   - Verify match conditions use valid operators (`==`, `!=`, `>`, `<`)
   - Run `python validate_config.py` to get detailed error messages
   - Fix any issues mentioned in the error output

4. **ngrok Connection Issues**: If ngrok can't establish a tunnel, verify your authentication token and check that your network allows outbound connections.

5. **Container Communication**: If containers can't communicate with each other, ensure they're on the same Docker network.

### Viewing Logs

To view logs for troubleshooting:

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs pokemon-proxy
docker-compose logs ngrok
```