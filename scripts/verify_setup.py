#!/usr/bin/env python3
"""
Complete setup verification script for Tulia API.

This script verifies that your Python 3.11 environment is properly configured
and all dependencies are working correctly.
"""
import sys
import subprocess
import os
from pathlib import Path


def check_python_version():
    """Verify Python 3.11 is being used."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    
    if version.major == 3 and version.minor == 11:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Perfect!")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Expected Python 3.11")
        return False


def check_virtual_environment():
    """Check if running in virtual environment."""
    print("\n🏠 Checking virtual environment...")
    
    if hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    ):
        print("✅ Running in virtual environment")
        print(f"   Virtual env path: {sys.prefix}")
        return True
    else:
        print("❌ Not running in virtual environment")
        print("   Run: source venv/bin/activate")
        return False


def check_django_setup():
    """Test Django configuration."""
    print("\n🌐 Checking Django setup...")
    
    try:
        # Test Django check command
        result = subprocess.run(
            [sys.executable, 'manage.py', 'check'],
            capture_output=True,
            text=True,
            check=False,
            cwd=os.getcwd()  # Ensure we're in the right directory
        )
        
        if result.returncode == 0:
            print("✅ Django configuration valid")
            return True
        else:
            print("❌ Django configuration issues:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False


def check_gunicorn():
    """Test gunicorn configuration."""
    print("\n🦄 Checking Gunicorn setup...")
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'gunicorn', 'config.wsgi:application', '--check-config'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print("✅ Gunicorn configuration valid")
            return True
        else:
            print("❌ Gunicorn configuration issues:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Gunicorn test failed: {e}")
        return False


def check_ai_packages():
    """Test AI/ML package imports."""
    print("\n🤖 Checking AI/ML packages...")
    
    ai_packages = [
        ('langchain', 'LangChain framework'),
        ('langgraph', 'LangGraph orchestration'),
        ('openai', 'OpenAI client'),
        ('tiktoken', 'Token counting'),
        ('google.generativeai', 'Google Gemini'),
    ]
    
    all_good = True
    for package, description in ai_packages:
        try:
            __import__(package)
            print(f"✅ {description}")
        except ImportError as e:
            print(f"❌ {description}: {e}")
            all_good = False
    
    return all_good


def check_document_processing():
    """Test document processing packages."""
    print("\n📄 Checking document processing...")
    
    doc_packages = [
        ('PyPDF2', 'PDF processing'),
        ('pdfplumber', 'Advanced PDF extraction'),
        ('docx', 'DOCX processing'),
        ('chardet', 'Character encoding detection'),
    ]
    
    all_good = True
    for package, description in doc_packages:
        try:
            __import__(package)
            print(f"✅ {description}")
        except ImportError as e:
            print(f"❌ {description}: {e}")
            all_good = False
    
    return all_good


def check_env_file():
    """Check if .env file exists and has basic configuration."""
    print("\n⚙️  Checking environment configuration...")
    
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found")
        print("   Copy .env.example to .env and configure")
        return False
    
    # Check for required variables
    required_vars = ['SECRET_KEY', 'DATABASE_URL', 'JWT_SECRET_KEY', 'ENCRYPTION_KEY']
    env_content = env_file.read_text()
    
    missing_vars = []
    for var in required_vars:
        if f"{var}=" not in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Environment configuration looks good")
        return True


def main():
    """Run all verification checks."""
    print("Tulia API Setup Verification")
    print("=" * 50)
    
    checks = [
        check_python_version,
        check_virtual_environment,
        check_env_file,
        check_django_setup,
        check_gunicorn,
        check_ai_packages,
        check_document_processing,
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    
    if all(results):
        print("🎉 All checks passed! Your setup is ready for production.")
        print("\nNext steps:")
        print("1. Add your AI provider API key to .env")
        print("2. Configure Redis if using Celery")
        print("3. Set up PostgreSQL for production")
        print("4. Deploy with: gunicorn config.wsgi:application")
        sys.exit(0)
    else:
        failed_count = len([r for r in results if not r])
        print(f"💥 {failed_count} checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()