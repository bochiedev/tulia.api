#!/bin/bash
# Script to verify that sensitive files have been removed from git history
# Task 1.5: Remove Hardcoded Secrets from Repository

set -e

echo "=================================================="
echo "Git History Cleanup Verification"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Files that should be removed
FILES_TO_CHECK=(
    ".env"
    "test_all_auth.py"
    "test_auth_endpoint.py"
    "comprehensive_api_test.py"
    "test_api_fixes.sh"
)

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo -e "${RED}ERROR: Not in a git repository root${NC}"
    exit 1
fi

echo "Checking git history for sensitive files..."
echo ""

FOUND_COUNT=0
CLEAN_COUNT=0

for file in "${FILES_TO_CHECK[@]}"; do
    echo -n "Checking $file... "
    
    # Check if file exists in any commit
    if git log --all --pretty=format: --name-only --diff-filter=A | grep -q "^$file$"; then
        echo -e "${RED}✗ FOUND IN HISTORY${NC}"
        FOUND_COUNT=$((FOUND_COUNT + 1))
        
        # Show which commits contain the file
        echo "  Commits containing this file:"
        git log --all --oneline --name-only --diff-filter=A | grep -B1 "^$file$" | grep -v "^$file$" | head -5
        echo ""
    else
        echo -e "${GREEN}✓ CLEAN${NC}"
        CLEAN_COUNT=$((CLEAN_COUNT + 1))
    fi
done

echo ""
echo "=================================================="
echo "Verification Results"
echo "=================================================="
echo ""
echo "Files checked: ${#FILES_TO_CHECK[@]}"
echo -e "Clean: ${GREEN}$CLEAN_COUNT${NC}"
echo -e "Found in history: ${RED}$FOUND_COUNT${NC}"
echo ""

# Check for common secret patterns in history
echo "Checking for secret patterns in git history..."
echo ""

PATTERNS=(
    "sk-[a-zA-Z0-9]{20,}:OpenAI API Key"
    "AKIA[0-9A-Z]{16}:AWS Access Key"
    "SG\.[a-zA-Z0-9_-]{22}\.:SendGrid API Key"
    "AC[a-f0-9]{32}:Twilio Account SID"
)

PATTERN_FOUND=0

for pattern_info in "${PATTERNS[@]}"; do
    IFS=':' read -r pattern name <<< "$pattern_info"
    echo -n "Checking for $name... "
    
    # Search in git history (limit to last 100 commits for performance)
    if git log --all -p -100 | grep -qE "$pattern"; then
        echo -e "${RED}✗ FOUND${NC}"
        PATTERN_FOUND=$((PATTERN_FOUND + 1))
        echo "  Pattern: $pattern"
        echo ""
    else
        echo -e "${GREEN}✓ CLEAN${NC}"
    fi
done

echo ""
echo "=================================================="
echo "Pattern Check Results"
echo "=================================================="
echo ""
echo "Patterns checked: ${#PATTERNS[@]}"
echo -e "Clean: ${GREEN}$((${#PATTERNS[@]} - PATTERN_FOUND))${NC}"
echo -e "Found: ${RED}$PATTERN_FOUND${NC}"
echo ""

# Repository statistics
echo "=================================================="
echo "Repository Statistics"
echo "=================================================="
echo ""
echo "Repository size:"
du -sh .git
echo ""
echo "Total commits:"
git rev-list --all --count
echo ""
echo "Branches:"
git branch -a | wc -l
echo ""

# Final verdict
echo "=================================================="
echo "Final Verdict"
echo "=================================================="
echo ""

if [ $FOUND_COUNT -eq 0 ] && [ $PATTERN_FOUND -eq 0 ]; then
    echo -e "${GREEN}✓ SUCCESS: Git history is clean!${NC}"
    echo ""
    echo "All sensitive files have been removed from git history."
    echo "No secret patterns detected in recent commits."
    echo ""
    echo "Next steps:"
    echo "1. Rotate all exposed secrets (see HARDCODED_SECRETS_AUDIT.md)"
    echo "2. Install pre-commit hooks to prevent future commits"
    echo "3. Update team on new security practices"
    exit 0
else
    echo -e "${RED}✗ FAILURE: Sensitive data still found in git history${NC}"
    echo ""
    echo "Issues found:"
    [ $FOUND_COUNT -gt 0 ] && echo "  - $FOUND_COUNT file(s) still in history"
    [ $PATTERN_FOUND -gt 0 ] && echo "  - $PATTERN_FOUND secret pattern(s) detected"
    echo ""
    echo "Recommended actions:"
    echo "1. Re-run the cleanup script: ./scripts/clean_git_history.sh"
    echo "2. Use more aggressive cleanup: git filter-branch"
    echo "3. Consider creating a fresh repository if cleanup fails"
    exit 1
fi
