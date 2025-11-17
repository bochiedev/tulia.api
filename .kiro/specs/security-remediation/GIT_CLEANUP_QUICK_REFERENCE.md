# Git History Cleanup - Quick Reference

**Task 1.5 Subtask:** Use BFG Repo-Cleaner to remove from git history

## Quick Start (3 Steps)

### 1. Run the Script
```bash
cd /path/to/tulia.api
./scripts/clean_git_history.sh
```

### 2. Review & Test
```bash
# Check size reduction
du -sh .git

# Verify files removed
git log --all --pretty=format: --name-only | grep -E "\.env$|test_.*auth"

# Run tests
pytest
```

### 3. Push to Remote (⚠️ Rewrites History!)
```bash
git push origin --force --all
git push origin --force --tags
```

## Files Being Removed

| File | Reason |
|------|--------|
| `.env` | Real production secrets (CRITICAL) |
| `test_all_auth.py` | Hardcoded JWT tokens |
| `test_auth_endpoint.py` | Hardcoded JWT tokens |
| `comprehensive_api_test.py` | Hardcoded credentials |
| `test_api_fixes.sh` | Hardcoded API keys |

## Team Coordination Checklist

After force-push, all team members must:

- [ ] Backup local work: `git stash` or `git format-patch`
- [ ] Delete local repo: `rm -rf tulia.api`
- [ ] Clone fresh: `git clone <repo-url>`
- [ ] Reapply work: `git stash pop` or `git am *.patch`

## Post-Cleanup Actions

- [ ] Rotate OpenAI API key
- [ ] Rotate SendGrid API key
- [ ] Rotate Sentry DSN
- [ ] Rotate Django SECRET_KEY
- [ ] Rotate JWT_SECRET_KEY
- [ ] Rotate ENCRYPTION_KEY
- [ ] Rotate all tenant API keys
- [ ] Install pre-commit hooks
- [ ] Update documentation

## Troubleshooting

**Script fails with "Java not found":**
```bash
# Ubuntu/Debian
sudo apt-get install default-jre

# macOS
brew install openjdk
```

**Files still in history:**
```bash
# Run more aggressive cleanup
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

**Force-push rejected:**
```bash
# Check you have permission
git remote -v

# May need to disable branch protection temporarily
```

## Alternative: Manual Method

If script doesn't work:

```bash
# Download BFG manually
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar -O bfg.jar

# Create file list
echo -e ".env\ntest_all_auth.py\ntest_auth_endpoint.py\ncomprehensive_api_test.py\ntest_api_fixes.sh" > files_to_remove.txt

# Run BFG
java -jar bfg.jar --delete-files files_to_remove.txt --no-blob-protection .

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Resources

- Full Guide: `.kiro/specs/security-remediation/GIT_HISTORY_CLEANUP_GUIDE.md`
- Security Audit: `.kiro/specs/security-remediation/HARDCODED_SECRETS_AUDIT.md`
- BFG Docs: https://rtyley.github.io/bfg-repo-cleaner/

## Estimated Time

- Script execution: 5-10 minutes
- Testing: 10-15 minutes
- Team coordination: 15-30 minutes
- **Total: 30-60 minutes**
