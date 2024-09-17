#!/usr/bin/env bash

# Load environment variables from .env file
if [ -f .env ]; then
    echo "Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
else
    echo ".env file not found!"
    exit 1
fi

# Confirm that the environment variables are loaded
echo "Environment variables loaded:"
grep -v '^#' .env

# installing dependencies
echo "Installing dependencies..."
npm install

# Deploy using Serverless Framework
echo "Starting serverless deployment..."
sudo serverless deploy

if [ $? -eq 0 ]; then
    echo "Serverless deploy succeeded."
else
    echo "Serverless deploy failed."
    exit 1
fi
