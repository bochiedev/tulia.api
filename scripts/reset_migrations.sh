#!/bin/bash
# Reset all migrations and create fresh ones
# This script removes all migration files and creates new ones based on current models

set -e  # Exit on any error

echo "🚀 Tulia AI Migration Reset"
echo "============================"

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
    print_error "manage.py not found. Run this script from the project root."
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected. Make sure you've activated it."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "This will:"
echo "1. Remove all existing migration files"
echo "2. Remove the database file"
echo "3. Create fresh migrations"
echo "4. Apply migrations"
echo "5. Seed initial data"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "🗑️  Removing existing migration files..."

# Remove migration files from all apps
for app_dir in apps/*/; do
    if [ -d "$app_dir" ]; then
        app_name=$(basename "$app_dir")
        migrations_dir="$app_dir/migrations"
        
        if [ -d "$migrations_dir" ]; then
            echo "  📁 Processing $app_name/migrations/"
            
            # Remove all .py files except __init__.py
            find "$migrations_dir" -name "*.py" ! -name "__init__.py" -delete
            
            # Remove __pycache__ directories
            find "$migrations_dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
            
            echo "    🗑️  Cleaned $app_name migrations"
        fi
    fi
done

print_status "Migration files removed"

echo ""
echo "🗄️  Removing database file..."

# Remove database files
for db_file in db.sqlite3 database.db tulia.db; do
    if [ -f "$db_file" ]; then
        rm "$db_file"
        echo "  🗑️  Removed $db_file"
    fi
done

print_status "Database file removed"

echo ""
echo "📝 Creating fresh migrations..."

# Create migrations
python manage.py makemigrations
if [ $? -ne 0 ]; then
    print_error "Failed to create migrations"
    exit 1
fi

print_status "Fresh migrations created"

echo ""
echo "🔄 Applying migrations to database..."

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

# Check platform settings
python manage.py check_platform_settings > /dev/null 2>&1
if [ $? -ne 0 ]; then
    print_warning "Platform settings check had warnings (this is normal)"
else
    print_status "Platform settings check passed"
fi

echo ""
echo "============================"
print_status "Migration reset completed successfully!"
echo ""
echo "Next steps:"
echo "1. Start the server: python manage.py runserver"
echo "2. Create superuser: python manage.py createsuperuser"
echo "3. Access admin: http://localhost:8000/admin"
echo "4. Test API: http://localhost:8000/v1/health/"