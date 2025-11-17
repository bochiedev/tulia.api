#!/bin/bash
#
# Pre-commit hook to detect secrets and sensitive data
# This hook prevents committing files that contain potential secrets
#

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

echo "🔍 Scanning staged files for secrets..."

# Flag to track if secrets were found
SECRETS_FOUND=0

# Patterns to detect (regex)
declare -a PATTERNS=(
    # API Keys and Tokens
    "AKIA[0-9A-Z]{16}"                                    # AWS Access Key
    "sk_live_[0-9a-zA-Z]{24,}"                           # Stripe Live Key
    "sk_test_[0-9a-zA-Z]{24,}"                           # Stripe Test Key
    "rk_live_[0-9a-zA-Z]{24,}"                           # Stripe Restricted Key
    "sq0atp-[0-9A-Za-z\-_]{22}"                          # Square Access Token
    "sq0csp-[0-9A-Za-z\-_]{43}"                          # Square OAuth Secret
    "access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}" # PayPal
    "amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" # Amazon MWS
    "AIza[0-9A-Za-z\-_]{35}"                             # Google API Key
    "ya29\.[0-9A-Za-z\-_]+"                              # Google OAuth
    "sk-[a-zA-Z0-9_-]{20,}"                              # OpenAI API Key (old format)
    "sk-proj-[a-zA-Z0-9_-]{20,}"                         # OpenAI API Key (new format)
    "ghp_[0-9a-zA-Z]{36}"                                # GitHub Personal Access Token
    "gho_[0-9a-zA-Z]{36}"                                # GitHub OAuth Token
    "github_pat_[0-9a-zA-Z]{22}_[0-9a-zA-Z]{59}"        # GitHub Fine-grained PAT
    "glpat-[0-9a-zA-Z\-_]{20}"                          # GitLab Personal Access Token
    "xox[baprs]-[0-9]{10,12}-[0-9]{10,12}-[0-9a-zA-Z]{24,}" # Slack Token
    "[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com" # Google OAuth Client
    "key-[0-9a-zA-Z]{32}"                                # Generic API Key
    "api[_-]?key['\"]?\s*[:=]\s*['\"][0-9a-zA-Z]{32,}['\"]" # API Key Assignment
    "secret[_-]?key['\"]?\s*[:=]\s*['\"][0-9a-zA-Z]{32,}['\"]" # Secret Key Assignment
    
    # JWT Tokens
    "eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}" # JWT Token
    
    # Private Keys
    "-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY"  # Private Key Headers
    "-----BEGIN CERTIFICATE-----"                         # Certificate
    
    # Database Connection Strings
    "postgres://[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@"         # PostgreSQL
    "mysql://[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@"            # MySQL
    "mongodb(\+srv)?://[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@"  # MongoDB
    
    # Generic Secrets (high confidence patterns)
    "password['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]"      # Password assignment
    "passwd['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]"        # Passwd assignment
    "pwd['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]"           # Pwd assignment
    "token['\"]?\s*[:=]\s*['\"][0-9a-zA-Z]{20,}['\"]"   # Token assignment
    "bearer [a-zA-Z0-9_\-\.=]+"                          # Bearer token
    
    # Twilio
    "AC[a-z0-9]{32}"                                     # Twilio Account SID
    "SK[a-z0-9]{32}"                                     # Twilio API Key
    
    # Slack Webhooks
    "https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8}/[a-zA-Z0-9_]{24}" # Slack Webhook
    
    # Generic High-Entropy Strings (likely secrets)
    "['\"][a-zA-Z0-9/+]{40,}={0,2}['\"]"                # Base64 encoded (40+ chars)
)

# Files to always check (even if not in patterns)
declare -a SENSITIVE_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    ".env.staging"
    "credentials.json"
    "service-account.json"
    "firebase-adminsdk.json"
    "id_rsa"
    "id_dsa"
    "id_ecdsa"
    "id_ed25519"
    "*.pem"
    "*.key"
    "*.p12"
    "*.pfx"
    "*.jks"
    "*.keystore"
)

# Function to check if file should be excluded from secret scanning
should_exclude_file() {
    local file="$1"
    
    # Exclude test files
    if [[ "$file" == *test*.py ]] || [[ "$file" == *_test.py ]] || [[ "$file" == */tests/* ]]; then
        return 0
    fi
    
    # Exclude documentation files
    if [[ "$file" == *.md ]]; then
        return 0
    fi
    
    # Exclude example files
    if [[ "$file" == *.example ]] || [[ "$file" == .example.* ]]; then
        return 0
    fi
    
    # Exclude docs directory
    if [[ "$file" == docs/* ]]; then
        return 0
    fi
    
    # Exclude spec files
    if [[ "$file" == .kiro/specs/* ]]; then
        return 0
    fi
    
    # Exclude postman collections
    if [[ "$file" == postman/* ]]; then
        return 0
    fi
    
    return 1  # Should not exclude
}

# Check for sensitive filenames
for file in $STAGED_FILES; do
    filename=$(basename "$file")
    
    # Check against sensitive file patterns
    for pattern in "${SENSITIVE_FILES[@]}"; do
        if [[ "$filename" == $pattern ]]; then
            echo -e "${RED}❌ ERROR: Attempting to commit sensitive file: $file${NC}"
            echo -e "${YELLOW}   This file type should never be committed.${NC}"
            SECRETS_FOUND=1
        fi
    done
    
    # Skip binary files and deleted files
    if [ ! -f "$file" ]; then
        continue
    fi
    
    # Check if file is binary
    if file "$file" | grep -q "binary"; then
        continue
    fi
    
    # Skip files that match exclude patterns
    if should_exclude_file "$file"; then
        continue
    fi
    
    # Scan file content for secret patterns
    for pattern in "${PATTERNS[@]}"; do
        matches=$(grep -nE "$pattern" "$file" 2>/dev/null || true)
        
        if [ ! -z "$matches" ]; then
            # Filter out false positives (documentation examples)
            # Check if matches are in docstrings, comments, or example sections
            filtered_matches=""
            while IFS= read -r match; do
                line_num=$(echo "$match" | cut -d: -f1)
                
                # Get context around the match (3 lines before)
                context=$(sed -n "$((line_num-3)),$((line_num))p" "$file" 2>/dev/null || echo "")
                
                # Skip if in docstring, comment, or example section
                if echo "$context" | grep -qE "('''|\"\"\"|\#|example|Example|EXAMPLE|OpenApiExample|request_only|value=|curl|bash)"; then
                    continue
                fi
                
                # Skip if line contains common example indicators
                if echo "$match" | grep -qE "(example\.com|your-password|your-email|SecurePass123|TestPass|test@|demo@)"; then
                    continue
                fi
                
                filtered_matches="$filtered_matches$match"$'\n'
            done <<< "$matches"
            
            # Only report if there are matches after filtering
            if [ ! -z "$filtered_matches" ] && [ "$filtered_matches" != $'\n' ]; then
                echo -e "${RED}❌ ERROR: Potential secret detected in: $file${NC}"
                echo -e "${YELLOW}   Pattern: $pattern${NC}"
                echo -e "${YELLOW}   Matches:${NC}"
                echo "$filtered_matches" | head -3 | while IFS= read -r line; do
                    if [ ! -z "$line" ]; then
                        echo -e "${YELLOW}     $line${NC}"
                    fi
                done
                SECRETS_FOUND=1
            fi
        fi
    done
done

# Check for common secret variable names in Python files
for file in $STAGED_FILES; do
    if [[ "$file" == *.py ]]; then
        # Skip files that match exclude patterns
        if should_exclude_file "$file"; then
            continue
        fi
        
        # Skip test files and example files
        if [[ "$file" == *test*.py ]] || [[ "$file" == *example*.py ]] || [[ "$file" == *.example.py ]] || [[ "$file" == */tests/* ]]; then
            continue
        fi
        
        # Check for hardcoded credentials in Python
        suspicious_vars=$(grep -nE "(API_KEY|SECRET_KEY|PASSWORD|TOKEN|PRIVATE_KEY|ACCESS_KEY|AUTH_TOKEN|BEARER_TOKEN|CLIENT_SECRET)\s*=\s*['\"][^'\"]{10,}['\"]" "$file" 2>/dev/null || true)
        
        if [ ! -z "$suspicious_vars" ]; then
            # Exclude Django settings patterns that use env()
            if ! echo "$suspicious_vars" | grep -q "env("; then
                echo -e "${RED}❌ ERROR: Hardcoded credential detected in: $file${NC}"
                echo -e "${YELLOW}   Suspicious assignments:${NC}"
                echo "$suspicious_vars" | head -3 | while IFS= read -r line; do
                    echo -e "${YELLOW}     $line${NC}"
                done
                SECRETS_FOUND=1
            fi
        fi
    fi
done

# Final result
if [ $SECRETS_FOUND -eq 1 ]; then
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  COMMIT BLOCKED: Secrets detected in staged files         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}What to do:${NC}"
    echo "  1. Remove the secrets from the files"
    echo "  2. Use environment variables instead (see .env.example)"
    echo "  3. Add sensitive files to .gitignore"
    echo "  4. If this is a false positive, you can bypass with:"
    echo "     git commit --no-verify"
    echo ""
    echo -e "${YELLOW}For more information, see:${NC}"
    echo "  - docs/SECURITY_BEST_PRACTICES.md"
    echo "  - .kiro/specs/security-remediation/GIT_HISTORY_CLEANUP_GUIDE.md"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ No secrets detected. Proceeding with commit.${NC}"
exit 0
