#!/usr/bin/env python3
"""
Dependency conflict checker for Tulia API.

This script helps identify potential dependency conflicts before deployment.
Run this after installing requirements to verify compatibility.
"""
import subprocess
import sys
from pathlib import Path


def run_pip_check():
    """Run pip check to identify dependency conflicts."""
    print("🔍 Checking for dependency conflicts...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print("✅ No dependency conflicts found!")
            return True
        else:
            print("❌ Dependency conflicts detected:")
            print(result.stdout)
            if result.stderr:
                print("Errors:")
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running pip check: {e}")
        return False


def check_critical_imports():
    """Test importing critical packages to ensure they work."""
    critical_packages = [
        "django",
        "rest_framework",
        "celery",
        "redis",
        "psycopg",
        "cryptography",
        "twilio",
        "openai",
        "langchain",
        "langgraph",
    ]
    
    print("\n🧪 Testing critical package imports...")
    failed_imports = []
    
    for package in critical_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError as e:
            print(f"❌ {package}: {e}")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"\n❌ Failed to import: {', '.join(failed_imports)}")
        return False
    else:
        print("\n✅ All critical packages imported successfully!")
        return True


def main():
    """Main function."""
    print("Tulia API Dependency Checker")
    print("=" * 40)
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    ):
        print("⚠️  Warning: Not running in a virtual environment")
        print("   Consider using: python -m venv venv && source venv/bin/activate")
    
    # Run checks
    pip_check_ok = run_pip_check()
    import_check_ok = check_critical_imports()
    
    print("\n" + "=" * 40)
    if pip_check_ok and import_check_ok:
        print("🎉 All dependency checks passed!")
        print("   Your environment is ready for production.")
        sys.exit(0)
    else:
        print("💥 Dependency issues detected!")
        print("   Consider using requirements-minimal.txt for a lighter installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()