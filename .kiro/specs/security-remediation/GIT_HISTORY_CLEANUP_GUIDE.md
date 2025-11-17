# Git History Cleanup Guide

**Task:** 1.5 - Remove Hardcoded Secrets from Repository  
**Subtask:** Use BFG Repo-Cleaner to remove from git history  
**Date:** 2025-11-17  
**Status:** Ready for execution

## Overview

This guide provides instructions for removing sensitive files from git history using BFG Repo-Cleaner. This is a critical security task to ensure that hardcoded secrets are completely removed from the repository.

## ⚠️ Important Warnings

1. **This operation rewrites git history** - All commit hashes will change
2. **Requires force-push** - If you've already pushed to remote
3. **Team coordination required** - All team members must re-clone after this operation
4. **Backup first** - The script creates a backup, but verify it exists
5. **Cannot be undone** - Once pushed to remote, the old history is gone

## Files to be Removed

Based on the security audit, the following files will be removed from git history:

1. `.env` - Contains real production secrets (CRITICAL)
2. `test_all_auth.py` - Contains hardcoded JWT tokens
3. `test_auth_endpoint.py` - Contains hardcoded JWT tokens
4. `comprehensive_api_test.py` - Contains hardcoded JWT tokens and API keys
5. `test_api_fixes.sh` - Contains hardcoded API keys

## Prerequisites

### Required Software

- **Git** - Already installed
- **Java** - Required to run BFG (already installed at `/usr/bin/java`)
- **wget or curl** - For downloading BFG (script will check)

### Before You Start

1. **Commit all changes:**
   ```bash
   git add .
   git commit -m "Prepare for git history cleanup"
   ```

2. **Notify team members:**
   - Inform them that git history will be rewritten
   - Ask them to backup their local work
   - Schedule a time when no one is actively pushing

3. **Verify backup location:**
   - The script will create a backup at `../tulia-backup-YYYYMMDD-HHMMSS`
   - Ensure you have enough disk space (repository size × 2)

## Execution Steps

### Step 1: Run the Cleanup Script

```bash
cd /path/to/tulia.api
./scripts/clean_git_history.sh
```

The script will:
1. Check for uncommitted changes
2. Create a backup of the entire repository
3. Download BFG Repo-Cleaner (if not present)
4. Verify Java installation
5. Create a list of files to remove
6. Show current repository statistics
7. Ask for confirmation
8. Run BFG to remove files from history
9. Clean up the repository with `git gc`
10. Verify files are removed
11. Show next steps

### Step 2: Review the Changes

After the script completes, review the changes:

```bash
# Check repository size reduction
du -sh .git

# Verify files are removed from history
git log --all --pretty=format: --name-only --diff-filter=A | grep -E "\.env$|test_all_auth\.py|test_auth_endpoint\.py|comprehensive_api_test\.py|test_api_fixes\.sh"

# Should return nothing if successful

# Check recent commits
git log --oneline --all | head -20
```

### Step 3: Test Locally

Before pushing to remote, test that everything still works:

```bash
# Run tests
pytest

# Start the application
python manage.py runserver

# Verify no critical functionality is broken
```

### Step 4: Push to Remote (If Applicable)

⚠️ **WARNING:** This will rewrite remote history!

```bash
# Force-push all branches
git push origin --force --all

# Force-push all tags
git push origin --force --tags
```

### Step 5: Team Coordination

After pushing to remote, all team members must:

1. **Backup their local work:**
   ```bash
   # Save any uncommitted changes
   git stash
   
   # Create a patch of local commits
   git format-patch origin/main
   ```

2. **Delete their local repository:**
   ```bash
   cd ..
   rm -rf tulia.api
   ```

3. **Clone fresh from remote:**
   ```bash
   git clone <repository-url>
   cd tulia.api
   ```

4. **Reapply their work:**
   ```bash
   # Apply patches if needed
   git am *.patch
   
   # Or restore stashed changes
   git stash pop
   ```

## What BFG Does

BFG Repo-Cleaner is a faster, simpler alternative to `git filter-branch` for removing unwanted data from git history.

### How It Works

1. **Scans all commits** - Looks through entire git history
2. **Removes specified files** - Deletes files from all commits where they appear
3. **Rewrites commits** - Creates new commits without the removed files
4. **Updates references** - Updates all branches and tags to point to new commits

### What It Doesn't Do

- **Doesn't modify HEAD** - Your current working directory is not changed
- **Doesn't remove from working directory** - Files in your current checkout remain
- **Doesn't affect .gitignore** - You still need to ensure files are ignored

## Verification Checklist

After running the script, verify:

- [ ] Script completed without errors
- [ ] Backup directory exists and contains full repository
- [ ] Repository size is reduced (check with `du -sh .git`)
- [ ] Files are not found in history (check with git log)
- [ ] Application still runs correctly
- [ ] Tests still pass
- [ ] No critical functionality is broken

## Troubleshooting

### Issue: "Not in a git repository root"

**Solution:** Run the script from the repository root directory:
```bash
cd /path/to/tulia.api
./scripts/clean_git_history.sh
```

### Issue: "Java is not installed"

**Solution:** Install Java:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install default-jre

# macOS
brew install openjdk
```

### Issue: "Files still found in history"

**Solution:** Some files may be protected. Try running BFG with `--no-blob-protection`:
```bash
java -jar bfg.jar --delete-files files_to_remove.txt --no-blob-protection .
```

### Issue: "Repository size didn't decrease"

**Solution:** Run git gc more aggressively:
```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Issue: "Force-push rejected"

**Solution:** Ensure you have permission to force-push:
```bash
# Check remote configuration
git remote -v

# If using GitHub, you may need to temporarily disable branch protection
```

## Alternative: Manual Cleanup with git filter-branch

If BFG doesn't work, you can use `git filter-branch`:

```bash
# Remove .env from all commits
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all

# Remove test files
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch test_all_auth.py test_auth_endpoint.py comprehensive_api_test.py test_api_fixes.sh' \
  --prune-empty --tag-name-filter cat -- --all

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

⚠️ **Note:** `git filter-branch` is much slower than BFG for large repositories.

## Post-Cleanup Actions

After successfully cleaning git history:

### 1. Rotate All Exposed Secrets

See `HARDCODED_SECRETS_AUDIT.md` for the complete list. Priority secrets to rotate:

- [ ] OpenAI API key
- [ ] SendGrid API key (EMAIL_HOST_PASSWORD)
- [ ] Sentry DSN
- [ ] Django SECRET_KEY
- [ ] JWT_SECRET_KEY
- [ ] ENCRYPTION_KEY
- [ ] All tenant API keys

### 2. Update Documentation

- [ ] Update `.env.example` with placeholder values
- [ ] Document secret rotation in CHANGELOG
- [ ] Update deployment documentation

### 3. Implement Prevention Measures

- [ ] Add pre-commit hooks (see next section)
- [ ] Enable GitHub secret scanning (if using GitHub)
- [ ] Train team on secret management

### 4. Clean Up Temporary Files

```bash
# Remove BFG jar
rm bfg.jar

# Remove file list
rm files_to_remove.txt

# Remove backup (after verifying everything works)
rm -rf ../tulia-backup-*
```

## Prevention: Pre-commit Hooks

To prevent future commits of secrets, install pre-commit hooks:

### Option 1: Simple Bash Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook to detect secrets

# Patterns to detect
PATTERNS=(
    "sk-[a-zA-Z0-9]{20,}"           # OpenAI API keys
    "AKIA[0-9A-Z]{16}"              # AWS access keys
    "eyJ[a-zA-Z0-9_-]{10,}\."       # JWT tokens
    "SG\.[a-zA-Z0-9_-]{22}\."       # SendGrid API keys
    "AC[a-f0-9]{32}"                # Twilio Account SIDs
)

# Check staged files
for pattern in "${PATTERNS[@]}"; do
    if git diff --cached --name-only | xargs grep -E "$pattern" 2>/dev/null; then
        echo "❌ ERROR: Potential secret detected in staged files"
        echo "Pattern: $pattern"
        echo "Please remove secrets before committing"
        exit 1
    fi
done

# Check for .env file
if git diff --cached --name-only | grep -q "^\.env$"; then
    echo "❌ ERROR: Attempting to commit .env file"
    echo "Please remove .env from staging"
    exit 1
fi

exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Option 2: git-secrets

Install and configure git-secrets:

```bash
# Install git-secrets
# macOS
brew install git-secrets

# Ubuntu/Debian
git clone https://github.com/awslabs/git-secrets.git
cd git-secrets
sudo make install

# Configure for repository
cd /path/to/tulia.api
git secrets --install
git secrets --register-aws
git secrets --add 'sk-[a-zA-Z0-9]{20,}'
git secrets --add 'eyJ[a-zA-Z0-9_-]{10,}\.'
git secrets --add 'SG\.[a-zA-Z0-9_-]{22}\.'
```

### Option 3: pre-commit Framework

Install pre-commit framework:

```bash
pip install pre-commit
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json
```

Install hooks:
```bash
pre-commit install
```

## Resources

- [BFG Repo-Cleaner Documentation](https://rtyley.github.io/bfg-repo-cleaner/)
- [Git Filter-Branch Documentation](https://git-scm.com/docs/git-filter-branch)
- [GitHub: Removing Sensitive Data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-secrets](https://github.com/awslabs/git-secrets)
- [pre-commit Framework](https://pre-commit.com/)

## Summary

This guide provides a comprehensive approach to removing sensitive files from git history using BFG Repo-Cleaner. The automated script handles the entire process, including:

- Backup creation
- BFG download and execution
- Repository cleanup
- Verification

After running the script, remember to:
1. Test locally
2. Force-push to remote (if applicable)
3. Coordinate with team for re-cloning
4. Rotate all exposed secrets
5. Implement prevention measures

**Estimated Time:** 30-60 minutes (depending on repository size)

**Risk Level:** Medium (requires force-push and team coordination)

**Success Criteria:**
- ✅ All sensitive files removed from git history
- ✅ Repository size reduced
- ✅ Application still works correctly
- ✅ Team successfully re-cloned
- ✅ Prevention measures in place
