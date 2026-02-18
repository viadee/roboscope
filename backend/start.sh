#!/bin/bash
# Start mateoX Backend mit sauberer Umgebung
cd "$(dirname "$0")"

# Bestehende DATABASE_URL aus Eltern-Prozess entfernen
unset DATABASE_URL

# .env wird von pydantic-settings automatisch geladen
source .venv/bin/activate
exec uvicorn src.main:app --reload --port 8000
