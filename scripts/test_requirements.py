#!/usr/bin/env python3
"""
Test script to verify requirements.txt has no conflicts.
Run this in a fresh virtual environment to test package installation.
"""
import subprocess
import sys
import os

def test_requirements():
    """Test that requirements.txt can be installed without conflicts."""
    print("🧪 Testing requirements.txt for conflicts...")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Not in a virtual environment")
    
    # Test dry run first
    print("📋 Running pip install --dry-run...")
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--dry-run', '-r', 'requirements.txt'
        ], capture_output=True, text=True, check=True)
        print("✅ Dry run successful - no conflicts detected")
    except subprocess.CalledProcessError as e:
        print(f"❌ Dry run failed: {e}")
        print(f"Error output: {e.stderr}")
        return False
    
    # Check for duplicate packages
    print("🔍 Checking for duplicate packages...")
    with open('requirements.txt', 'r') as f:
        lines = f.readlines()
    
    packages = {}
    duplicates = []
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if line and not line.startswith('#'):
            if '==' in line:
                package_name = line.split('==')[0].strip()
                if package_name in packages:
                    duplicates.append(f"Line {line_num}: {line} (duplicate of line {packages[package_name]})")
                else:
                    packages[package_name] = line_num
    
    if duplicates:
        print("❌ Duplicate packages found:")
        for dup in duplicates:
            print(f"  {dup}")
        return False
    else:
        print("✅ No duplicate packages found")
    
    print("🎉 Requirements.txt validation successful!")
    return True

if __name__ == "__main__":
    success = test_requirements()
    sys.exit(0 if success else 1)