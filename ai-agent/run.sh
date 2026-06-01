#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting AI Agent"

exec python3 -u /app/main.py
