#!/bin/bash
# Server cleanup script to fix migration issues
# Run this on your server to clean up old migration files

set -e  # Exit on any error

echo "🧹 Tulia AI Server Cleanup"
echo "=========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    print_error "manage.py not found. Run this script from the project root (/srv/tulia.api)."
    exit 1
fi

echo "This script will:"
echo "1. Remove ALL migration files (except __init__.py)"
echo "2. Remove database file"
echo "3. Remove Python cache files"
echo "4. Create fresh migrations"
echo "5. Apply migrations"
echo "6. Seed initial data"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "🗑️  Cleaning up old files..."

# Remove ALL migration files except __init__.py
echo "  📁 Removing migration files..."
find apps/*/migrations/ -name "*.py" ! -name "__init__.py" -delete 2>/dev/null || true
find apps/*/migrations/ -name "*.pyc" -delete 2>/dev/null || true

# Remove __pycache__ directories
echo "  📁 Removing cache directories..."
find apps/*/migrations/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find apps/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove database files
echo "  🗄️  Removing database files..."
rm -f db.sqlite3 database.db tulia.db

print_status "Cleanup completed"

echo ""
echo "📝 Creating fresh migrations..."

# Activate virtual environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "venv/bin/activate" ]; then
        echo "  🐍 Activating virtual environment..."
        source venv/bin/activate
    else
        print_error "Virtual environment not found. Please activate it manually."
        exit 1
    fi
fi

# Create migrations
python manage.py makemigrations
if [ $? -ne 0 ]; then
    print_error "Failed to create migrations"
    exit 1
fi

print_status "Fresh migrations created"

echo ""
echo "🔄 Applying migrations..."

# Apply migrations
python manage.py migrate
if [ $? -ne 0 ]; then
    print_error "Failed to apply migrations"
    exit 1
fi

print_status "Migrations applied successfully"

echo ""
echo "🌱 Seeding initial data..."

# Seed permissions
echo "  📋 Seeding permissions..."
python manage.py seed_permissions
if [ $? -ne 0 ]; then
    print_error "Failed to seed permissions"
    exit 1
fi

# Seed subscription tiers
echo "  💰 Seeding subscription tiers..."
python manage.py seed_subscription_tiers
if [ $? -ne 0 ]; then
    print_error "Failed to seed subscription tiers"
    exit 1
fi

# Seed platform settings
echo "  ⚙️  Seeding platform settings..."
python manage.py seed_platform_settings
if [ $? -ne 0 ]; then
    print_error "Failed to seed platform settings"
    exit 1
fi

print_status "Initial data seeded successfully"

echo ""
echo "🔍 Verifying setup..."

# Run Django check
python manage.py check
if [ $? -ne 0 ]; then
    print_error "Django check failed"
    exit 1
fi

print_status "Django check passed"

echo ""
echo "=========================="
print_status "Server cleanup completed successfully!"
echo ""
echo "Your server is now ready. You can:"
echo "1. Start the server: python manage.py runserver 0.0.0.0:8000"
echo "2. Create superuser: python manage.py createsuperuser"
echo "3. Access admin: http://your-server:8000/admin"
echo "4. Test API: http://your-server:8000/v1/health/"