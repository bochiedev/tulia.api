#!/usr/bin/env python3
"""
Comprehensive installation verification script for Tulia AI.
Run this after installation to verify everything is working correctly.
"""
import subprocess
import sys
import os
import importlib

def check_python_version():
    """Check Python version."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} (compatible)")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (requires 3.11+)")
        return False

def check_virtual_environment():
    """Check if running in virtual environment."""
    print("📦 Checking virtual environment...")
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    if in_venv:
        print(f"✅ Virtual environment active: {sys.prefix}")
        return True
    else:
        print("❌ Not in virtual environment")
        return False

def check_required_packages():
    """Check if required packages are installed."""
    print("📚 Checking required packages...")
    
    # Get installed packages from pip
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'list', '--format=freeze'
        ], capture_output=True, text=True, check=True)
        
        installed = {}
        for line in result.stdout.strip().split('\n'):
            if '==' in line:
                package, version = line.split('==', 1)
                installed[package.lower()] = version
    except subprocess.CalledProcessError:
        print("❌ Failed to get installed packages")
        return False
    
    required_packages = [
        'django',
        'djangorestframework', 
        'celery',
        'redis',
        'psycopg',
        'gunicorn',
        'twilio',
        'openai',
        'langchain',
        'langgraph'
    ]
    
    missing_packages = []
    installed_packages = []
    
    for package in required_packages:
        if package.lower() in installed:
            installed_packages.append(f"{package} ({installed[package.lower()]})")
            print(f"  ✅ {package}")
        else:
            missing_packages.append(package)
            print(f"  ❌ {package}")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print(f"\n✅ All {len(installed_packages)} required packages installed")
        return True

def check_django_setup():
    """Check Django configuration."""
    print("🎯 Checking Django setup...")
    
    try:
        # Change to the directory containing manage.py
        original_dir = os.getcwd()
        
        # Add current directory to Python path
        if original_dir not in sys.path:
            sys.path.insert(0, original_dir)
        
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        print("✅ Django configuration loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def check_management_commands():
    """Check if management commands are available."""
    print("⚙️  Checking management commands...")
    
    try:
        from django.core.management import get_commands
        commands = get_commands()
        
        required_commands = [
            'seed_permissions',
            'seed_subscription_tiers', 
            'seed_platform_settings',
            'check_platform_settings',
            'test_email'
        ]
        
        missing_commands = []
        available_commands = []
        
        for cmd in required_commands:
            if cmd in commands:
                available_commands.append(cmd)
                print(f"  ✅ {cmd}")
            else:
                missing_commands.append(cmd)
                print(f"  ❌ {cmd}")
        
        if missing_commands:
            print(f"\n❌ Missing commands: {', '.join(missing_commands)}")
            return False
        else:
            print(f"\n✅ All {len(available_commands)} management commands available")
            return True
            
    except Exception as e:
        print(f"❌ Failed to check management commands: {e}")
        return False

def check_database():
    """Check database connectivity."""
    print("🗄️  Checking database...")
    
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Run: python manage.py migrate")
        return False

def check_environment_file():
    """Check if .env file exists and has required variables."""
    print("🔧 Checking environment configuration...")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("Run: cp .env.example .env")
        return False
    
    required_vars = [
        'SECRET_KEY',
        'JWT_SECRET_KEY', 
        'ENCRYPTION_KEY'
    ]
    
    missing_vars = []
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    for var in required_vars:
        if f"{var}=" not in env_content or f"{var}=your-" in env_content:
            missing_vars.append(var)
            print(f"  ❌ {var} not configured")
        else:
            print(f"  ✅ {var}")
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Environment configuration looks good")
        return True

def run_django_check():
    """Run Django system check."""
    print("🔍 Running Django system check...")
    
    try:
        result = subprocess.run([
            sys.executable, 'manage.py', 'check'
        ], capture_output=True, text=True, check=True)
        print("✅ Django system check passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Django system check failed:")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    """Run all verification checks."""
    print("🚀 Tulia AI Installation Verification")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_environment),
        ("Required Packages", check_required_packages),
        ("Django Setup", check_django_setup),
        ("Management Commands", check_management_commands),
        ("Environment File", check_environment_file),
        ("Database Connection", check_database),
        ("Django System Check", run_django_check),
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n{name}:")
        try:
            if check_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name} check failed with error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Installation verification successful!")
        print("\nNext steps:")
        print("1. python manage.py seed_permissions")
        print("2. python manage.py seed_subscription_tiers") 
        print("3. python manage.py seed_platform_settings")
        print("4. python manage.py runserver")
        return True
    else:
        print("❌ Installation verification failed!")
        print(f"{total - passed} issues need to be resolved.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)