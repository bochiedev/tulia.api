#!/bin/bash
# Quick activation script for Tulia AI development environment
# Usage: source activate.sh

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    echo "📍 Project: Tulia AI WhatsApp Commerce Platform"
    echo "🐍 Python: $(python --version)"
    echo "📦 Django: $(python -c 'import django; print(django.get_version())')"
    echo ""
    echo "Quick commands:"
    echo "  make run       - Start development server"
    echo "  make test      - Run tests"
    echo "  make shell     - Django shell"
    echo "  make migrate   - Run migrations"
    echo ""
else
    echo "❌ Virtual environment not found!"
    echo "Run: ./scripts/setup.sh"
fi
