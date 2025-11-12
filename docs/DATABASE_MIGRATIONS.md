# Database Migrations Guide

This guide covers database migration management for the Tulia AI WhatsApp Commerce Platform.

## Table of Contents

1. [Overview](#overview)
2. [Migration Workflow](#migration-workflow)
3. [Creating Migrations](#creating-migrations)
4. [Applying Migrations](#applying-migrations)
5. [Migration Best Practices](#migration-best-practices)
6. [Rollback Procedures](#rollback-procedures)
7. [Data Migrations](#data-migrations)
8. [Production Migration Checklist](#production-migration-checklist)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Django migrations are version control for your database schema. They allow you to:
- Track changes to models over time
- Apply schema changes consistently across environments
- Rollback changes if needed
- Migrate data alongside schema changes

### Migration Files Location

Migrations are stored in each app's `migrations/` directory:

```
apps/
├── tenants/
│   └── migrations/
│       ├── 0001_initial.py
│       ├── 0002_add_subscription_fields.py
│       └── __init__.py
├── catalog/
│   └── migrations/
│       ├── 0001_initial.py
│       └── __init__.py
└── ...
```

---

## Migration Workflow

### Development Workflow

```
1. Modify models.py
   ↓
2. Create migration: python manage.py makemigrations
   ↓
3. Review migration file
   ↓
4. Test migration: python manage.py migrate
   ↓
5. Verify changes in database
   ↓
6. Commit migration file to Git
```

### Production Workflow

```
1. Test migrations in staging environment
   ↓
2. Backup production database
   ↓
3. Put application in maintenance mode (if needed)
   ↓
4. Apply migrations: python manage.py migrate
   ↓
5. Verify migration success
   ↓
6. Restart application services
   ↓
7. Monitor for errors
   ↓
8. Remove maintenance mode
```

---

## Creating Migrations

### Automatic Migration Creation

When you modify models, Django can automatically detect changes:

```bash
# Create migrations for all apps
python manage.py makemigrations

# Create migration for specific app
python manage.py makemigrations tenants

# Create migration with custom name
python manage.py makemigrations tenants --name add_subscription_fields

# Dry run (show what would be created)
python manage.py makemigrations --dry-run

# Create empty migration for data migration
python manage.py makemigrations --empty tenants --name migrate_tenant_credentials
```

### Migration File Structure

A typical migration file:

```python
# apps/tenants/migrations/0002_add_subscription_fields.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='subscription_tier',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='tenants.subscriptiontier'
            ),
        ),
        migrations.AddField(
            model_name='tenant',
            name='trial_start_date',
            field=models.DateTimeField(null=True),
        ),
    ]
```

### Common Migration Operations

#### Adding a Field

```python
migrations.AddField(
    model_name='tenant',
    name='new_field',
    field=models.CharField(max_length=255, default=''),
)
```

#### Removing a Field

```python
migrations.RemoveField(
    model_name='tenant',
    name='old_field',
)
```

#### Renaming a Field

```python
migrations.RenameField(
    model_name='tenant',
    old_name='old_field',
    new_name='new_field',
)
```

#### Adding an Index

```python
migrations.AddIndex(
    model_name='customer',
    index=models.Index(fields=['tenant', 'phone_e164'], name='customer_tenant_phone_idx'),
)
```

#### Creating a Model

```python
migrations.CreateModel(
    name='NewModel',
    fields=[
        ('id', models.UUIDField(primary_key=True, default=uuid.uuid4)),
        ('name', models.CharField(max_length=255)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
    ],
)
```

---

## Applying Migrations

### Basic Migration Commands

```bash
# Apply all pending migrations
python manage.py migrate

# Apply migrations for specific app
python manage.py migrate tenants

# Apply up to specific migration
python manage.py migrate tenants 0002

# Show migration status
python manage.py showmigrations

# Show SQL for a migration (without applying)
python manage.py sqlmigrate tenants 0002

# List all migrations
python manage.py showmigrations --list

# Show plan without applying
python manage.py migrate --plan
```

### Migration Status Output

```bash
$ python manage.py showmigrations

tenants
 [X] 0001_initial
 [X] 0002_add_subscription_fields
 [ ] 0003_add_wallet_models

catalog
 [X] 0001_initial
 [X] 0002_add_product_variants
```

- `[X]` = Applied
- `[ ]` = Pending

---

## Migration Best Practices

### 1. Always Review Generated Migrations

Before committing, review the migration file:

```bash
# View the migration file
cat apps/tenants/migrations/0002_add_subscription_fields.py

# View the SQL that will be executed
python manage.py sqlmigrate tenants 0002
```

### 2. Test Migrations Locally First

```bash
# Create a test database
createdb tulia_test

# Apply migrations to test database
DATABASE_URL=postgresql://user:pass@localhost/tulia_test python manage.py migrate

# Verify the changes
DATABASE_URL=postgresql://user:pass@localhost/tulia_test python manage.py dbshell
```

### 3. Keep Migrations Small and Focused

**Good**: One migration per logical change
```
0002_add_subscription_tier.py
0003_add_trial_dates.py
0004_add_wallet_model.py
```

**Bad**: One migration with many unrelated changes
```
0002_add_everything.py  # Contains subscription, wallet, and analytics changes
```

### 4. Use Descriptive Migration Names

```bash
# Good names
python manage.py makemigrations tenants --name add_subscription_tier
python manage.py makemigrations catalog --name add_product_search_index

# Bad names (auto-generated)
0002_auto_20250112_1234.py
```

### 5. Handle Nullable Fields Carefully

When adding a non-nullable field to an existing table:

**Option 1**: Add with default value
```python
migrations.AddField(
    model_name='tenant',
    name='status',
    field=models.CharField(max_length=20, default='active'),
)
```

**Option 2**: Add as nullable, populate, then make non-nullable
```python
# Migration 1: Add nullable field
migrations.AddField(
    model_name='tenant',
    name='status',
    field=models.CharField(max_length=20, null=True),
)

# Migration 2: Populate data (data migration)
# ... populate status field ...

# Migration 3: Make non-nullable
migrations.AlterField(
    model_name='tenant',
    name='status',
    field=models.CharField(max_length=20, default='active'),
)
```

### 6. Use Transactions

Django migrations run in transactions by default. For operations that can't run in transactions:

```python
class Migration(migrations.Migration):
    atomic = False  # Disable transaction wrapping

    operations = [
        # Operations that can't run in a transaction
    ]
```

### 7. Avoid Destructive Operations

Be cautious with:
- `RemoveField`: Data will be lost
- `DeleteModel`: All data will be lost
- `RenameField`: Can cause issues if not done carefully

Always backup before destructive operations.

---

## Rollback Procedures

### Rolling Back Migrations

```bash
# Rollback to previous migration
python manage.py migrate tenants 0001

# Rollback all migrations for an app
python manage.py migrate tenants zero

# Show what would be rolled back
python manage.py migrate tenants 0001 --plan
```

### Rollback Workflow

1. **Identify the target migration**:
   ```bash
   python manage.py showmigrations tenants
   ```

2. **Backup the database**:
   ```bash
   pg_dump -U tulia_user tulia_db > backup_before_rollback.sql
   ```

3. **Rollback to target migration**:
   ```bash
   python manage.py migrate tenants 0001
   ```

4. **Verify the rollback**:
   ```bash
   python manage.py showmigrations tenants
   python manage.py dbshell
   ```

5. **Restart services**:
   ```bash
   sudo systemctl restart tulia-web tulia-celery-worker
   ```

### Handling Failed Migrations

If a migration fails mid-way:

```bash
# 1. Check migration status
python manage.py showmigrations

# 2. If partially applied, mark as not applied
python manage.py migrate --fake tenants 0001

# 3. Fix the migration file

# 4. Re-apply the migration
python manage.py migrate tenants 0002
```

---

## Data Migrations

Data migrations transform existing data without changing schema.

### Creating a Data Migration

```bash
# Create empty migration
python manage.py makemigrations --empty tenants --name migrate_tenant_credentials
```

### Data Migration Template

```python
# apps/tenants/migrations/0005_migrate_tenant_credentials.py

from django.db import migrations

def migrate_credentials_forward(apps, schema_editor):
    """Move credentials from Tenant to TenantSettings."""
    Tenant = apps.get_model('tenants', 'Tenant')
    TenantSettings = apps.get_model('tenants', 'TenantSettings')
    
    for tenant in Tenant.objects.all():
        # Get or create settings
        settings, created = TenantSettings.objects.get_or_create(tenant=tenant)
        
        # Migrate data
        if tenant.twilio_sid:
            settings.twilio_sid = tenant.twilio_sid
        if tenant.twilio_token:
            settings.twilio_token = tenant.twilio_token
        
        settings.save()

def migrate_credentials_backward(apps, schema_editor):
    """Reverse migration: move credentials back to Tenant."""
    Tenant = apps.get_model('tenants', 'Tenant')
    TenantSettings = apps.get_model('tenants', 'TenantSettings')
    
    for settings in TenantSettings.objects.all():
        tenant = settings.tenant
        tenant.twilio_sid = settings.twilio_sid
        tenant.twilio_token = settings.twilio_token
        tenant.save()

class Migration(migrations.Migration):
    dependencies = [
        ('tenants', '0004_create_tenant_settings'),
    ]

    operations = [
        migrations.RunPython(
            migrate_credentials_forward,
            reverse_code=migrate_credentials_backward,
        ),
    ]
```

### Data Migration Best Practices

1. **Always provide reverse operations** for rollback
2. **Use `apps.get_model()`** instead of importing models directly
3. **Process data in batches** for large datasets:
   ```python
   batch_size = 1000
   for i in range(0, total_count, batch_size):
       batch = Model.objects.all()[i:i+batch_size]
       # Process batch
   ```
4. **Add progress logging** for long-running migrations
5. **Test with production-like data volumes**

---

## Production Migration Checklist

### Pre-Migration

- [ ] Review all pending migrations
- [ ] Test migrations in staging environment
- [ ] Verify migration SQL with `sqlmigrate`
- [ ] Estimate migration duration
- [ ] Create database backup
- [ ] Schedule maintenance window (if needed)
- [ ] Notify stakeholders
- [ ] Prepare rollback plan

### During Migration

- [ ] Put application in maintenance mode (if needed)
- [ ] Stop Celery workers (if schema changes affect tasks)
- [ ] Apply migrations: `python manage.py migrate`
- [ ] Verify migration success: `python manage.py showmigrations`
- [ ] Check database for expected changes
- [ ] Restart application services
- [ ] Run smoke tests

### Post-Migration

- [ ] Monitor error logs
- [ ] Check Sentry for new errors
- [ ] Verify critical user flows
- [ ] Monitor database performance
- [ ] Remove maintenance mode
- [ ] Update documentation
- [ ] Notify stakeholders of completion

### Rollback Checklist

- [ ] Identify target migration for rollback
- [ ] Stop application services
- [ ] Restore database from backup (if needed)
- [ ] Rollback migrations: `python manage.py migrate app_name target_migration`
- [ ] Restart application services
- [ ] Verify rollback success
- [ ] Investigate root cause
- [ ] Plan fix and re-deployment

---

## Troubleshooting

### Issue: Inconsistent Migration History

**Error**: `InconsistentMigrationHistory: Migration X is applied before its dependency Y`

**Solution**:
```bash
# Option 1: Fake the dependency
python manage.py migrate --fake app_name migration_number

# Option 2: Reset migrations (DESTRUCTIVE - development only)
python manage.py migrate app_name zero
python manage.py migrate app_name
```

### Issue: Migration Conflicts

**Error**: `Conflicting migrations detected; multiple leaf nodes in the migration graph`

**Solution**:
```bash
# Merge migrations
python manage.py makemigrations --merge

# Review and edit the merge migration if needed
```

### Issue: Circular Dependencies

**Error**: `CircularDependencyError: Circular dependency in migrations`

**Solution**:
1. Identify the circular dependency in migration files
2. Reorder dependencies or split migrations
3. Use `run_before` instead of `dependencies` if appropriate

### Issue: Long-Running Migration

**Problem**: Migration takes too long, blocking deployment

**Solutions**:
1. **Add index concurrently** (PostgreSQL):
   ```python
   migrations.RunSQL(
       'CREATE INDEX CONCURRENTLY idx_name ON table_name (column_name);',
       reverse_sql='DROP INDEX CONCURRENTLY idx_name;',
   )
   ```

2. **Split into multiple migrations**:
   - Migration 1: Add nullable field
   - Migration 2: Populate data (can run in background)
   - Migration 3: Make field non-nullable

3. **Use background tasks**:
   - Apply schema change
   - Use Celery task to populate data
   - Apply constraint in later migration

### Issue: Failed Migration with Partial Changes

**Problem**: Migration failed mid-way, database in inconsistent state

**Solution**:
```bash
# 1. Restore from backup
psql -U tulia_user tulia_db < backup_before_migration.sql

# 2. Or manually fix the database and fake the migration
python manage.py migrate --fake app_name migration_number

# 3. Fix the migration file and re-apply
python manage.py migrate
```

### Issue: Migration Works Locally but Fails in Production

**Common Causes**:
1. Different PostgreSQL versions
2. Different data volumes
3. Missing database extensions
4. Permission issues

**Solution**:
```bash
# Test with production-like data
pg_dump -U prod_user prod_db | psql -U local_user local_db
python manage.py migrate

# Check PostgreSQL version compatibility
python manage.py dbshell
SELECT version();
```

---

## Advanced Topics

### Squashing Migrations

Combine multiple migrations into one:

```bash
# Squash migrations 0001 through 0010
python manage.py squashmigrations tenants 0001 0010

# Review the squashed migration
# Delete old migrations after verifying
```

### Custom Migration Operations

```python
from django.db import migrations

class CustomOperation(migrations.RunPython):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        # Custom forward logic
        pass
    
    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Custom backward logic
        pass
```

### Zero-Downtime Migrations

For large production systems:

1. **Phase 1**: Add new field (nullable)
2. **Deploy**: Application writes to both old and new fields
3. **Phase 2**: Backfill data
4. **Deploy**: Application reads from new field
5. **Phase 3**: Remove old field

---

## Monitoring and Maintenance

### Regular Checks

```bash
# Check for unapplied migrations
python manage.py showmigrations | grep "\[ \]"

# Check for migration conflicts
python manage.py makemigrations --check --dry-run

# Verify database schema matches models
python manage.py migrate --check
```

### Database Maintenance

```bash
# Analyze tables after large migrations
python manage.py dbshell
ANALYZE;

# Vacuum tables to reclaim space
VACUUM ANALYZE;

# Reindex if needed
REINDEX DATABASE tulia_db;
```

---

## Additional Resources

- **Django Migrations**: https://docs.djangoproject.com/en/4.2/topics/migrations/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Migration Best Practices**: https://docs.djangoproject.com/en/4.2/howto/writing-migrations/

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
