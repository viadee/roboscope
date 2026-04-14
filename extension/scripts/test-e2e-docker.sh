#!/bin/bash
# Run E2E tests in Docker container
set -e
cd "$(dirname "$0")/.."
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
