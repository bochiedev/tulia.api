# Server Setup Guide

Quick setup guide for your Ubuntu server.

## Current Issue

The error you're seeing indicates that `celery` is not installed, even though it's in requirements.txt. This suggests the pip installation didn't complete successfully.

## Quick Fix

Run these commands on your server:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Verify you're in the right directory
pwd  # Should show /srv/tulia.api

# 3. Check what's actually installed
pip list | grep -E "(django|celery|redis)"

# 4. If packages are missing, reinstall
pip install --upgrade pip
pip install -r requirements.txt

# 5. Verify celery is installed
python -c "import celery; print('Celery version:', celery.__version__)"

# 6. Test Django setup
python manage.py check

# 7. If Django check passes, run the seeding commands
python manage.py seed_permissions
python manage.py seed_subscription_tiers
python manage.py seed_platform_settings
```

## Complete Fresh Installation

If the above doesn't work, do a complete fresh installation:

```bash
# 1. Go to your project directory
cd /srv/tulia.api

# 2. Remove old virtual environment
rm -rf venv

# 3. Create fresh virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 4. Upgrade pip
pip install --upgrade pip

# 5. Install requirements
pip install -r requirements.txt

# 6. Verify installation
pip list | grep -E "(django|celery|redis|gunicorn)"

# 7. Check Django
python manage.py check

# 8. Run migrations
python manage.py migrate

# 9. Seed data
python manage.py seed_permissions
python manage.py seed_subscription_tiers  
python manage.py seed_platform_settings

# 10. Test platform settings
python manage.py check_platform_settings
```

## Troubleshooting

### If pip install fails:

```bash
# Clear pip cache
pip cache purge

# Try installing with no cache
pip install --no-cache-dir -r requirements.txt

# Or install packages individually to see which one fails
pip install django==4.2.16
pip install celery==5.3.6
pip install redis==5.0.8
```

### If you get permission errors:

```bash
# Make sure you own the directory
sudo chown -R ubuntu:ubuntu /srv/tulia.api

# Make sure virtual environment is activated
source venv/bin/activate
```

### If Django can't find modules:

```bash
# Make sure you're in the project root directory
cd /srv/tulia.api

# Check PYTHONPATH
echo $PYTHONPATH

# Add current directory to path if needed
export PYTHONPATH=/srv/tulia.api:$PYTHONPATH
```

## Verification Commands

After installation, run these to verify everything works:

```bash
# Check Python version
python --version  # Should be 3.11+

# Check virtual environment
which python  # Should point to /srv/tulia.api/venv/bin/python

# Check key packages
python -c "import django; print('Django:', django.__version__)"
python -c "import celery; print('Celery:', celery.__version__)"
python -c "import redis; print('Redis client installed')"

# Check Django setup
python manage.py check

# Check management commands
python manage.py help | grep seed

# Test database connection
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('Database OK')"
```

## Environment Configuration

Make sure your `.env` file has the required settings:

```bash
# Check if .env exists
ls -la .env

# If not, copy from example
cp .env.example .env

# Edit with your settings
nano .env
```

Required variables in `.env`:
- `SECRET_KEY` - Django secret key
- `JWT_SECRET_KEY` - JWT authentication key  
- `ENCRYPTION_KEY` - For encrypting sensitive data
- `DEBUG=False` - For production
- `ALLOWED_HOSTS=your-domain.com,your-ip-address`

## Running the Application

### Development Mode:
```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### Production Mode:
```bash
source venv/bin/activate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## Common Issues

1. **"No module named 'celery'"** - Requirements not installed properly
2. **"No module named 'config'"** - Not in project root directory
3. **"seed_permissions command not found"** - Django apps not loaded properly
4. **Permission denied** - Directory ownership issues

## Getting Help

If you're still having issues, run this diagnostic command and share the output:

```bash
cd /srv/tulia.api
source venv/bin/activate
echo "=== System Info ==="
python --version
which python
pwd
echo "=== Installed Packages ==="
pip list | head -20
echo "=== Django Check ==="
python manage.py check 2>&1 || echo "Django check failed"
echo "=== Environment ==="
ls -la .env 2>/dev/null || echo ".env not found"
```