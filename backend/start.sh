#!/bin/bash
# Start mateoX Backend mit sauberer Umgebung
cd "$(dirname "$0")"

# Bestehende DATABASE_URL etc. aus Eltern-Prozess entfernen
unset DATABASE_URL
unset REDIS_URL
unset CELERY_BROKER_URL
unset CELERY_RESULT_BACKEND

# .env wird von pydantic-settings automatisch geladen
source .venv/bin/activate
exec uvicorn src.main:app --reload --port 8000
