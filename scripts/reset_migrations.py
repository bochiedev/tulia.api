#!/usr/bin/env python3
"""
Reset all migrations and create fresh ones based on current models.
This script will:
1. Remove all migration files (except __init__.py)
2. Create fresh initial migrations
3. Apply migrations to database
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def remove_migration_files():
    """Remove all migration files except __init__.py"""
    print("🗑️  Removing existing migration files...")
    
    apps_dir = Path("apps")
    removed_count = 0
    
    for app_dir in apps_dir.iterdir():
        if app_dir.is_dir() and not app_dir.name.startswith('__'):
            migrations_dir = app_dir / "migrations"
            if migrations_dir.exists():
                print(f"  📁 Processing {app_dir.name}/migrations/")
                
                for migration_file in migrations_dir.iterdir():
                    if (migration_file.is_file() and 
                        migration_file.name.endswith('.py') and 
                        migration_file.name != '__init__.py'):
                        
                        print(f"    🗑️  Removing {migration_file.name}")
                        migration_file.unlink()
                        removed_count += 1
                
                # Also remove __pycache__ if it exists
                pycache_dir = migrations_dir / "__pycache__"
                if pycache_dir.exists():
                    shutil.rmtree(pycache_dir)
                    print(f"    🗑️  Removed __pycache__")
    
    print(f"✅ Removed {removed_count} migration files")
    return removed_count > 0

def remove_database():
    """Remove SQLite database file"""
    print("🗄️  Removing database file...")
    
    db_files = ["db.sqlite3", "database.db", "tulia.db"]
    removed = False
    
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"  🗑️  Removed {db_file}")
            removed = True
    
    if not removed:
        print("  ℹ️  No database file found")
    
    return True

def create_migrations():
    """Create fresh migrations for all apps"""
    print("📝 Creating fresh migrations...")
    
    try:
        # Create migrations for all apps
        result = subprocess.run([
            sys.executable, "manage.py", "makemigrations"
        ], capture_output=True, text=True, check=True)
        
        print("✅ Fresh migrations created successfully")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create migrations: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def apply_migrations():
    """Apply migrations to database"""
    print("🔄 Applying migrations to database...")
    
    try:
        result = subprocess.run([
            sys.executable, "manage.py", "migrate"
        ], capture_output=True, text=True, check=True)
        
        print("✅ Migrations applied successfully")
        print(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to apply migrations: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def seed_initial_data():
    """Seed initial required data"""
    print("🌱 Seeding initial data...")
    
    commands = [
        "seed_permissions",
        "seed_subscription_tiers", 
        "seed_platform_settings"
    ]
    
    for command in commands:
        try:
            print(f"  📋 Running {command}...")
            result = subprocess.run([
                sys.executable, "manage.py", command
            ], capture_output=True, text=True, check=True)
            
            print(f"  ✅ {command} completed")
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {command} failed: {e}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return False
    
    print("✅ Initial data seeded successfully")
    return True

def verify_setup():
    """Verify the setup is working"""
    print("🔍 Verifying setup...")
    
    try:
        # Run Django check
        result = subprocess.run([
            sys.executable, "manage.py", "check"
        ], capture_output=True, text=True, check=True)
        
        print("✅ Django check passed")
        
        # Check platform settings
        result = subprocess.run([
            sys.executable, "manage.py", "check_platform_settings"
        ], capture_output=True, text=True, check=True)
        
        print("✅ Platform settings check passed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Verification failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def main():
    """Main function to reset migrations"""
    print("🚀 Tulia AI Migration Reset")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists("manage.py"):
        print("❌ Error: manage.py not found. Run this script from the project root.")
        sys.exit(1)
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Virtual environment not detected. Make sure you've activated it.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    print("\nThis will:")
    print("1. Remove all existing migration files")
    print("2. Remove the database file")
    print("3. Create fresh migrations")
    print("4. Apply migrations")
    print("5. Seed initial data")
    
    response = input("\nContinue? (y/N): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        sys.exit(0)
    
    # Execute steps
    steps = [
        ("Remove migration files", remove_migration_files),
        ("Remove database", remove_database),
        ("Create migrations", create_migrations),
        ("Apply migrations", apply_migrations),
        ("Seed initial data", seed_initial_data),
        ("Verify setup", verify_setup)
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Failed at step: {step_name}")
            sys.exit(1)
    
    print("\n" + "=" * 40)
    print("🎉 Migration reset completed successfully!")
    print("\nNext steps:")
    print("1. Start the server: python manage.py runserver")
    print("2. Create superuser: python manage.py createsuperuser")
    print("3. Access admin: http://localhost:8000/admin")

if __name__ == "__main__":
    main()