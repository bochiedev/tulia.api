# Clean Installation Guide

This guide provides step-by-step instructions for installing Tulia AI on a fresh server without conflicts.

## Prerequisites

- Python 3.11+ installed
- Git installed
- Virtual environment support

## Installation Steps

### 1. Clone Repository

```bash
git clone <repository-url>
cd tulia.api
```

### 2. Create Fresh Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv
# OR if Python 3.11 is your default:
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows
```

### 3. Upgrade pip

```bash
pip install --upgrade pip
```

### 4. Test Requirements (Optional)

```bash
# Test for conflicts before installation
python scripts/test_requirements.py
```

### 5. Install Dependencies

```bash
# Install all production dependencies
pip install -r requirements.txt

# OR for development (includes testing tools)
pip install -r requirements-dev.txt
```

### 6. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env  # or your preferred editor
```

### 7. Database Setup

```bash
# Run migrations
python manage.py migrate

# Seed required data
python manage.py seed_permissions
python manage.py seed_subscription_tiers
python manage.py seed_platform_settings
```

### 8. Verify Installation

```bash
# Check for issues
python manage.py check

# Test platform settings
python manage.py check_platform_settings

# Test email service
python manage.py test_email --email test@example.com --name "Test User"
```

### 9. Run Application

```bash
# Development server
python manage.py runserver

# Production server (after configuring gunicorn)
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

## Troubleshooting

### Package Conflicts

If you encounter package conflicts:

1. **Check for duplicates**:
   ```bash
   python scripts/test_requirements.py
   ```

2. **Clear pip cache**:
   ```bash
   pip cache purge
   ```

3. **Reinstall in fresh environment**:
   ```bash
   deactivate
   rm -rf venv
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Common Issues

**"Cannot install X and Y because these package versions have conflicting dependencies"**
- This indicates duplicate packages in requirements.txt
- Run the test script to identify duplicates
- Report the issue if found

**"No module named 'apps.core.middleware'"**
- Missing `__init__.py` files in middleware directory
- This should be fixed in the current version

**Migration errors**
- Delete `db.sqlite3` and run `python manage.py migrate` again
- This resets the database with clean migrations

## Verification Checklist

- [ ] Virtual environment activated
- [ ] All packages installed without conflicts
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Platform settings seeded
- [ ] Django check passes
- [ ] Server starts successfully
- [ ] API health endpoint responds

## Support

If you encounter issues:

1. Run the test script: `python scripts/test_requirements.py`
2. Check the logs for specific error messages
3. Verify Python version: `python --version` (should be 3.11+)
4. Ensure virtual environment is activated

## Production Notes

- Use PostgreSQL instead of SQLite for production
- Configure Redis for caching and Celery
- Set `DEBUG=False` in production
- Use gunicorn or similar WSGI server
- Configure proper security settings