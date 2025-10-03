#!/usr/bin/env bash
# Load environment variables from .env into the current shell

if [[ ! -f ".env" ]]; then
  echo ".env file not found in $(pwd)"
  exit 1
fi

# Export all key=value pairs, ignoring comments and empty lines
export $(grep -v '^#' .env | xargs -d '\n')
