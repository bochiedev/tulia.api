# Pre-Commit Hook Quick Reference

## Installation

```bash
./scripts/install_git_hooks.sh
```

## What It Does

Automatically scans all staged files for secrets before allowing commits.

## Detected Patterns

### API Keys
- AWS Access Keys (`AKIA...`)
- Stripe Keys (`sk_live_...`, `sk_test_...`)
- OpenAI Keys (`sk-...`, `sk-proj-...`)
- GitHub Tokens (`ghp_...`, `gho_...`)
- GitLab Tokens (`glpat-...`)
- Slack Tokens (`xox...`)
- Google API Keys (`AIza...`)
- Twilio Credentials (`AC...`, `SK...`)

### Tokens & Secrets
- JWT Tokens (full format)
- Bearer Tokens
- Generic API Keys
- Password Assignments
- Token Assignments

### Private Keys
- RSA/DSA/EC Private Keys
- OpenSSH Keys
- PGP Keys
- Certificates

### Database Credentials
- PostgreSQL Connection Strings
- MySQL Connection Strings
- MongoDB Connection Strings

### Sensitive Files
- `.env` files
- `*.key`, `*.pem`, `*.p12` files
- `credentials.json`
- `service-account.json`
- Private key files

## Example: Blocked Commit

```bash
$ git commit -m "Add config"
🔍 Scanning staged files for secrets...
❌ ERROR: Potential secret detected in: config.py
   Pattern: sk-proj-[a-zA-Z0-9_-]{20,}
   Matches:
     42: OPENAI_API_KEY = "sk-proj-abc123..."

╔════════════════════════════════════════════════════════════╗
║  COMMIT BLOCKED: Secrets detected in staged files         ║
╚════════════════════════════════════════════════════════════╝
```

## Example: Allowed Commit

```bash
$ git commit -m "Add config"
🔍 Scanning staged files for secrets...
✅ No secrets detected. Proceeding with commit.
[main abc1234] Add config
 1 file changed, 5 insertions(+)
```

## Bypassing the Hook

**⚠️ USE WITH EXTREME CAUTION**

```bash
git commit --no-verify
```

Only bypass if you're absolutely certain it's a false positive.

## Common False Positives

### Test Files
The hook skips files matching:
- `*test*.py`
- `*example*.py`
- `*.example.py`

### Environment Variable Usage
These are allowed:
```python
# ✅ ALLOWED
API_KEY = env('API_KEY')
SECRET = os.getenv('SECRET')
TOKEN = settings.TOKEN
```

These are blocked:
```python
# ❌ BLOCKED
API_KEY = "sk-proj-abc123..."
SECRET = "my-secret-key-12345"
TOKEN = "eyJhbGciOiJIUzI1NiIs..."
```

## Troubleshooting

### Hook Not Running

```bash
# Check if hook is installed
ls -la .git/hooks/pre-commit

# Reinstall
./scripts/install_git_hooks.sh
```

### Hook Fails to Execute

```bash
# Make sure it's executable
chmod +x .git/hooks/pre-commit

# Check for syntax errors
bash -n .git/hooks/pre-commit
```

### False Positive

If the hook incorrectly flags something:

1. **First, verify it's actually safe**
2. Check if it matches a known pattern
3. Consider refactoring to avoid the pattern
4. If necessary, bypass with `--no-verify`
5. Report the false positive to the team

## What to Do When Blocked

1. **Remove the secret** from the file
2. **Use environment variables** instead:
   ```python
   # Instead of:
   API_KEY = "sk-proj-abc123..."
   
   # Use:
   API_KEY = env('API_KEY')
   ```
3. **Add to .env** (which is gitignored):
   ```bash
   echo 'API_KEY=sk-proj-abc123...' >> .env
   ```
4. **Update .env.example** (without real values):
   ```bash
   echo 'API_KEY=your-api-key-here' >> .env.example
   ```

## Testing the Hook

```bash
# Create a test file with a fake secret
echo 'API_KEY="sk-proj-test123456789"' > test.py

# Try to commit it
git add test.py
git commit -m "Test"

# Should be blocked!

# Clean up
git reset HEAD test.py
rm test.py
```

## Maintenance

### Update the Hook

```bash
# Pull latest changes
git pull

# Reinstall hook
./scripts/install_git_hooks.sh
```

### Customize Patterns

Edit `.git/hooks/pre-commit` to add custom patterns:

```bash
# Add to PATTERNS array
"your-custom-pattern"
```

## Resources

- **Full Documentation**: `.kiro/specs/security-remediation/SECRET_MANAGEMENT.md`
- **Hook Script**: `scripts/pre-commit-hook.sh`
- **Installation Script**: `scripts/install_git_hooks.sh`
- **Security Best Practices**: `docs/SECURITY_BEST_PRACTICES.md`

## Quick Commands

```bash
# Install hook
./scripts/install_git_hooks.sh

# Test hook
git commit --allow-empty -m "Test"

# Bypass hook (caution!)
git commit --no-verify

# Check hook status
ls -la .git/hooks/pre-commit

# View hook content
cat .git/hooks/pre-commit
```

## Support

If you have questions:
1. Check this guide
2. Review SECRET_MANAGEMENT.md
3. Contact the security team
4. Create a security ticket

**Remember: When in doubt, don't commit! Ask first.**
