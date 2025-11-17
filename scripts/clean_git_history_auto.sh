#!/bin/bash
# Automated script to clean sensitive files from git history using BFG Repo-Cleaner
# Task 1.5: Remove Hardcoded Secrets from Repository
# This version runs without user interaction (for CI/CD or automated workflows)

set -e  # Exit on error

echo "=================================================="
echo "Git History Cleaning Script (Automated)"
echo "Task 1.5: Remove Hardcoded Secrets from Repository"
echo "=================================================="
echo ""

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "ERROR: Not in a git repository root"
    exit 1
fi

# Download BFG if not present
BFG_JAR="bfg.jar"
if [ ! -f "$BFG_JAR" ]; then
    echo "Downloading BFG Repo-Cleaner..."
    BFG_VERSION="1.14.0"
    BFG_URL="https://repo1.maven.org/maven2/com/madgag/bfg/${BFG_VERSION}/bfg-${BFG_VERSION}.jar"
    
    if command -v wget &> /dev/null; then
        wget -q -O "$BFG_JAR" "$BFG_URL"
    elif command -v curl &> /dev/null; then
        curl -sL -o "$BFG_JAR" "$BFG_URL"
    else
        echo "ERROR: Neither wget nor curl found"
        exit 1
    fi
    echo "✓ BFG downloaded"
fi

# Check Java
if ! command -v java &> /dev/null; then
    echo "ERROR: Java is not installed"
    exit 1
fi

# Create list of files to remove
cat > files_to_remove.txt << 'EOF'
.env
test_all_auth.py
test_auth_endpoint.py
comprehensive_api_test.py
test_api_fixes.sh
EOF

echo "Files to remove from history:"
cat files_to_remove.txt
echo ""

# Show current repository size
echo "Repository size before cleaning:"
du -sh .git

# Run BFG to remove files
echo ""
echo "Running BFG Repo-Cleaner..."
java -jar "$BFG_JAR" --delete-files files_to_remove.txt --no-blob-protection .

# Clean up repository
echo ""
echo "Cleaning up repository..."
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Show new repository size
echo ""
echo "Repository size after cleaning:"
du -sh .git

echo ""
echo "✓ Git history cleaning completed"
echo ""
echo "Next steps:"
echo "1. Review changes: git log --oneline | head -20"
echo "2. Force-push: git push origin --force --all"
echo "3. Rotate all exposed secrets"
echo ""
