#!/bin/bash
# Script to clean sensitive files from git history using BFG Repo-Cleaner
# Task 1.5: Remove Hardcoded Secrets from Repository

set -e  # Exit on error

echo "=================================================="
echo "Git History Cleaning Script"
echo "Task 1.5: Remove Hardcoded Secrets from Repository"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo -e "${RED}ERROR: Not in a git repository root${NC}"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}WARNING: You have uncommitted changes${NC}"
    echo "Please commit or stash your changes before running this script"
    echo ""
    echo "Current changes:"
    git status --short
    echo ""
    read -p "Do you want to continue anyway? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Aborting."
        exit 1
    fi
fi

# Create backup
echo -e "${YELLOW}Step 1: Creating backup${NC}"
BACKUP_DIR="../tulia-backup-$(date +%Y%m%d-%H%M%S)"
echo "Creating backup at: $BACKUP_DIR"
cd ..
cp -r "$(basename "$OLDPWD")" "$BACKUP_DIR"
cd -
echo -e "${GREEN}✓ Backup created${NC}"
echo ""

# Download BFG if not present
BFG_JAR="bfg.jar"
if [ ! -f "$BFG_JAR" ]; then
    echo -e "${YELLOW}Step 2: Downloading BFG Repo-Cleaner${NC}"
    BFG_VERSION="1.14.0"
    BFG_URL="https://repo1.maven.org/maven2/com/madgag/bfg/${BFG_VERSION}/bfg-${BFG_VERSION}.jar"
    
    echo "Downloading from: $BFG_URL"
    if command -v wget &> /dev/null; then
        wget -O "$BFG_JAR" "$BFG_URL"
    elif command -v curl &> /dev/null; then
        curl -L -o "$BFG_JAR" "$BFG_URL"
    else
        echo -e "${RED}ERROR: Neither wget nor curl found. Please install one of them.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ BFG downloaded${NC}"
else
    echo -e "${GREEN}Step 2: BFG already downloaded${NC}"
fi
echo ""

# Check Java
echo -e "${YELLOW}Step 3: Checking Java installation${NC}"
if ! command -v java &> /dev/null; then
    echo -e "${RED}ERROR: Java is not installed${NC}"
    echo "Please install Java to use BFG Repo-Cleaner"
    exit 1
fi
JAVA_VERSION=$(java -version 2>&1 | head -n 1)
echo "Java found: $JAVA_VERSION"
echo -e "${GREEN}✓ Java is available${NC}"
echo ""

# Create list of files to remove
echo -e "${YELLOW}Step 4: Creating list of files to remove${NC}"
cat > files_to_remove.txt << 'EOF'
.env
test_all_auth.py
test_auth_endpoint.py
comprehensive_api_test.py
test_api_fixes.sh
EOF

echo "Files to remove from history:"
cat files_to_remove.txt
echo -e "${GREEN}✓ File list created${NC}"
echo ""

# Show current repository size
echo -e "${YELLOW}Step 5: Current repository statistics${NC}"
echo "Repository size before cleaning:"
du -sh .git
echo ""
COMMIT_COUNT=$(git rev-list --all --count)
echo "Total commits: $COMMIT_COUNT"
echo ""

# Confirm before proceeding
echo -e "${RED}WARNING: This will rewrite git history!${NC}"
echo "This operation will:"
echo "  1. Remove specified files from ALL commits"
echo "  2. Rewrite commit hashes"
echo "  3. Require force-push if already pushed to remote"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Aborting."
    exit 1
fi
echo ""

# Run BFG to remove files
echo -e "${YELLOW}Step 6: Running BFG Repo-Cleaner${NC}"
echo "Removing files from git history..."
java -jar "$BFG_JAR" --delete-files files_to_remove.txt --no-blob-protection .
echo -e "${GREEN}✓ BFG completed${NC}"
echo ""

# Clean up repository
echo -e "${YELLOW}Step 7: Cleaning up repository${NC}"
echo "Running git reflog expire..."
git reflog expire --expire=now --all
echo ""
echo "Running git gc (this may take a while)..."
git gc --prune=now --aggressive
echo -e "${GREEN}✓ Repository cleaned${NC}"
echo ""

# Show new repository size
echo -e "${YELLOW}Step 8: New repository statistics${NC}"
echo "Repository size after cleaning:"
du -sh .git
echo ""

# Verify files are removed
echo -e "${YELLOW}Step 9: Verifying files are removed${NC}"
echo "Checking if files still exist in history..."
FOUND_FILES=0
while IFS= read -r file; do
    if git log --all --pretty=format: --name-only --diff-filter=A | grep -q "^$file$"; then
        echo -e "${RED}✗ File still found in history: $file${NC}"
        FOUND_FILES=$((FOUND_FILES + 1))
    else
        echo -e "${GREEN}✓ File removed from history: $file${NC}"
    fi
done < files_to_remove.txt
echo ""

if [ $FOUND_FILES -gt 0 ]; then
    echo -e "${RED}WARNING: Some files may still exist in history${NC}"
    echo "You may need to run additional cleanup"
else
    echo -e "${GREEN}✓ All files successfully removed from history${NC}"
fi
echo ""

# Show next steps
echo "=================================================="
echo -e "${GREEN}Git history cleaning completed!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Review the changes:"
echo "   git log --oneline --all | head -20"
echo ""
echo "2. If you have a remote repository, force-push the changes:"
echo "   ${RED}WARNING: This will rewrite remote history!${NC}"
echo "   git push origin --force --all"
echo "   git push origin --force --tags"
echo ""
echo "3. Notify all team members to:"
echo "   - Backup their local work"
echo "   - Delete their local repository"
echo "   - Clone fresh from remote"
echo ""
echo "4. Clean up temporary files:"
echo "   rm bfg.jar"
echo "   rm files_to_remove.txt"
echo "   rm -rf $BACKUP_DIR  # After verifying everything works"
echo ""
echo "5. Rotate all exposed secrets (see HARDCODED_SECRETS_AUDIT.md)"
echo ""
echo -e "${YELLOW}Backup location: $BACKUP_DIR${NC}"
echo ""
