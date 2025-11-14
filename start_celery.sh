#!/bin/bash
# Start Celery worker for Tulia AI bot processing

echo "Starting Celery worker..."
echo "Press Ctrl+C to stop"
echo ""

source venv/bin/activate
celery -A config worker -l info
