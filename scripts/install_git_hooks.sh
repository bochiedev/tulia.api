#!/bin/bash
#
# Install Git Hooks for Secret Detection
# This script installs the pre-commit hook to detect secrets
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Installing Git Hooks for Secret Detection                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ ERROR: Not in a git repository${NC}"
    echo "Please run this script from the root of the repository"
    exit 1
fi

# Source and destination paths
HOOK_SOURCE="scripts/pre-commit-hook.sh"
HOOK_DEST=".git/hooks/pre-commit"

# Check if source hook exists
if [ ! -f "$HOOK_SOURCE" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Hook source file not found at $HOOK_SOURCE${NC}"
    echo "Creating hook from embedded template..."
    
    # Create the hook directory if it doesn't exist
    mkdir -p "$(dirname "$HOOK_SOURCE")"
    
    # Copy the hook from .git/hooks if it exists
    if [ -f "$HOOK_DEST" ]; then
        cp "$HOOK_DEST" "$HOOK_SOURCE"
        echo -e "${GREEN}✅ Extracted hook template to $HOOK_SOURCE${NC}"
    else
        echo -e "${RED}❌ ERROR: No hook template found${NC}"
        echo "Please ensure the pre-commit hook exists in .git/hooks/pre-commit"
        exit 1
    fi
fi

# Backup existing hook if present
if [ -f "$HOOK_DEST" ]; then
    BACKUP_FILE="${HOOK_DEST}.backup.$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}📦 Backing up existing hook to: $BACKUP_FILE${NC}"
    cp "$HOOK_DEST" "$BACKUP_FILE"
fi

# Install the hook
echo -e "${BLUE}📥 Installing pre-commit hook...${NC}"
cp "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

# Verify installation
if [ -x "$HOOK_DEST" ]; then
    echo -e "${GREEN}✅ Pre-commit hook installed successfully!${NC}"
else
    echo -e "${RED}❌ ERROR: Failed to install hook${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete                                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}What happens now:${NC}"
echo "  • Every commit will be scanned for secrets"
echo "  • Commits with secrets will be blocked"
echo "  • You'll see clear error messages if secrets are detected"
echo ""
echo -e "${BLUE}To bypass the hook (use with caution):${NC}"
echo "  git commit --no-verify"
echo ""
echo -e "${BLUE}For more information:${NC}"
echo "  • docs/SECURITY_BEST_PRACTICES.md"
echo "  • .kiro/specs/security-remediation/SECRET_MANAGEMENT.md"
echo ""
echo -e "${YELLOW}Testing the hook...${NC}"

# Test the hook
if "$HOOK_DEST" 2>&1 | grep -q "No secrets detected\|No staged files"; then
    echo -e "${GREEN}✅ Hook is working correctly${NC}"
else
    echo -e "${YELLOW}⚠️  Hook test completed (check output above)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Setup complete! Your commits are now protected.${NC}"
