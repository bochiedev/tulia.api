#!/bin/bash
# Setup script for Tulia AI development environment

set -e

echo "🚀 Setting up Tulia AI development environment..."
echo ""

# Check Python version
echo "📋 Checking Python version..."
python3 --version
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate
echo ""

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --quiet --upgrade pip setuptools wheel
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "📦 Installing dependencies (this may take a minute)..."
pip install --quiet -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    
    # Generate SECRET_KEY
    echo "🔑 Generating SECRET_KEY..."
    SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    
    # Generate ENCRYPTION_KEY
    echo "🔐 Generating ENCRYPTION_KEY..."
    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
    
    echo "✅ .env file created with generated keys"
else
    echo "✅ .env file already exists"
fi
echo ""

# Create logs directory
mkdir -p logs
echo "✅ Logs directory created"
echo ""

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --no-input
echo "✅ Migrations complete"
echo ""

# Run tests
echo "🧪 Running tests..."
pytest apps/core/tests/ -q
echo "✅ Tests passed"
echo ""

# Check Django configuration
echo "🔍 Checking Django configuration..."
python manage.py check
echo "✅ Configuration valid"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete! Tulia AI is ready for development."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 Quick Start:"
echo ""
echo "  1. Activate virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Start development server:"
echo "     python manage.py runserver"
echo ""
echo "  3. Visit http://localhost:8000/v1/health/"
echo ""
echo "  4. View API docs at http://localhost:8000/schema/swagger/"
echo ""
echo "📖 For more information, see:"
echo "   - SETUP_SUCCESS.md - Setup summary and next steps"
echo "   - README.md - Full documentation"
echo "   - QUICKSTART.md - Quick start guide"
echo ""
echo "🎉 Happy coding!"
echo ""
