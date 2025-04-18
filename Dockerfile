FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DEFAULT_RATE_LIMIT=120/minute \
    STREAM_RATE_LIMIT=100/minute

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
        protobuf-compiler \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy proto file first to generate Python code
COPY pokemon.proto .
RUN mkdir -p app/models && \
    protoc --python_out=app/models pokemon.proto

# Copy validation script first for config validation
COPY validate_config.py .

# Copy the rest of the application
COPY . .

# Make sure the generated file isn't overwritten
RUN if [ -f "app/models/pokemon_pb2.py" ]; then \
        echo "Using generated protobuf file"; \
    else \
        echo "Error: protobuf file not generated correctly"; \
        exit 1; \
    fi

# Validate the config.json file at build time
# Prevents building containers with invalid configuration
RUN echo "Validating configuration file before startup..." && \
    python validate_config.py

# Run the application
CMD ["python", "run.py"] 