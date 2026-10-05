#!/usr/bin/env bash

set -euo pipefail

# Resolve paths relative to this script, even when invoked outside the project.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Load environment variables from .env file
if [ -f .env ]; then
    echo "Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
else
    echo ".env file not found!"
    exit 1
fi

echo "Environment variables loaded."

# installing dependencies
echo "Installing dependencies..."
npm install

# Deploy using Serverless Framework
echo "Starting serverless deployment..."
if npx --no-install serverless deploy; then
    echo "Serverless deploy succeeded."
else
    echo "Serverless deploy failed."
    exit 1
fi
