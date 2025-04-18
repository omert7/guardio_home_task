#!/bin/bash
# Start script for Pokemon Streaming Proxy with config validation

# Set default config path if not provided
export POKEPROXY_CONFIG=${POKEPROXY_CONFIG:-config.json}

# Display header
echo "===================================="
echo "Pokemon Streaming Proxy Service"
echo "===================================="
echo "Config file: $POKEPROXY_CONFIG"

# First validate the configuration file
echo -e "\nValidating configuration file..."
python validate_config.py

# Check if validation was successful
if [ $? -ne 0 ]; then
  echo -e "\n❌ Config validation failed! Please fix the errors and try again."
  exit 1
fi

# If we get here, validation was successful
echo -e "\n✅ Config validation passed! Starting service..."

# Start the application
python run.py 