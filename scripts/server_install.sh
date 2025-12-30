#!/bin/bash
# Server Installation Script for Tulia AI
# Run this on your server to set up the complete environment

set -e  # Exit on any error

echo "🚀 Tulia AI Server Installation"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Don't run this script as root. Use a regular user with sudo access."
    exit 1
fi

# Check Python version
echo "🐍 Checking Python version..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    print_status "Python 3.11 found"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [ "$PYTHON_VERSION" = "3.11" ] || [ "$PYTHON_VERSION" = "3.12" ]; then
        PYTHON_CMD="python3"
        print_status "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.11+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3.11+ not found. Please install Python 3.11+"
    exit 1
fi

# Create virtual environment
echo "📦 Setting up virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists, removing..."
    rm -rf venv
fi

$PYTHON_CMD -m venv venv
source venv/bin/activate
print_status "Virtual environment created and activated"

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip
print_status "Pip upgraded"

# Test requirements for conflicts
echo "🧪 Testing requirements for conflicts..."
if [ -f "scripts/test_requirements.py" ]; then
    python scripts/test_requirements.py
    if [ $? -ne 0 ]; then
        print_error "Requirements test failed. Please check for conflicts."
        exit 1
    fi
    print_status "Requirements test passed"
else
    print_warning "Requirements test script not found, skipping..."
fi

# Install requirements
echo "📚 Installing Python packages..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    print_error "Failed to install requirements"
    exit 1
fi
print_status "Python packages installed successfully"

# Check environment file
echo "🔧 Checking environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warning ".env file created from template. Please configure it with your settings."
    else
        print_error ".env.example not found. Cannot create .env file."
        exit 1
    fi
else
    print_status ".env file exists"
fi

# Run verification script
echo "🔍 Running installation verification..."
if [ -f "scripts/verify_installation.py" ]; then
    python scripts/verify_installation.py
    if [ $? -ne 0 ]; then
        print_error "Installation verification failed"
        exit 1
    fi
    print_status "Installation verification passed"
else
    print_warning "Verification script not found, skipping..."
fi

# Run Django checks
echo "🎯 Running Django system check..."
python manage.py check
if [ $? -ne 0 ]; then
    print_error "Django system check failed"
    exit 1
fi
print_status "Django system check passed"

# Database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate
if [ $? -ne 0 ]; then
    print_error "Database migrations failed"
    exit 1
fi
print_status "Database migrations completed"

# Seed data
echo "🌱 Seeding initial data..."

echo "  📋 Seeding permissions..."
python manage.py seed_permissions
if [ $? -ne 0 ]; then
    print_error "Failed to seed permissions"
    exit 1
fi

echo "  💰 Seeding subscription tiers..."
python manage.py seed_subscription_tiers
if [ $? -ne 0 ]; then
    print_error "Failed to seed subscription tiers"
    exit 1
fi

echo "  ⚙️  Seeding platform settings..."
python manage.py seed_platform_settings
if [ $? -ne 0 ]; then
    print_error "Failed to seed platform settings"
    exit 1
fi

print_status "Initial data seeded successfully"

# Final verification
echo "🔍 Running final verification..."
python manage.py check_platform_settings
if [ $? -ne 0 ]; then
    print_error "Platform settings check failed"
    exit 1
fi

echo ""
echo "🎉 Installation completed successfully!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Configure your .env file with:"
echo "   - AI provider API keys (OPENAI_API_KEY, etc.)"
echo "   - Email service credentials (SENDGRID_API_KEY, etc.)"
echo "   - SMS service credentials (AFRICASTALKING_*, etc.)"
echo ""
echo "2. Start the development server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver 0.0.0.0:8000"
echo ""
echo "3. For production, use gunicorn:"
echo "   gunicorn config.wsgi:application --bind 0.0.0.0:8000"
echo ""
echo "4. Access your application:"
echo "   - API: http://your-server:8000"
echo "   - Admin: http://your-server:8000/admin"
echo "   - API Docs: http://your-server:8000/schema/swagger/"
echo ""
print_status "Installation guide complete!"