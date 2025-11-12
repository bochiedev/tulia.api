# PostgreSQL Driver Migration: psycopg2 → psycopg3

## Overview

The project has been upgraded from `psycopg2-binary` (v2.9.9) to `psycopg[binary]` (v3.2.3). This is a major version upgrade that provides better performance, improved type safety, and native async support.

## What Changed

### Dependencies
- **Before**: `psycopg2-binary==2.9.9`
- **After**: `psycopg[binary]==3.2.3`

### Compatibility
- ✅ Django 4.2+ fully supports psycopg3
- ✅ All existing code remains compatible (no breaking changes for our usage)
- ✅ Connection pooling settings unchanged
- ✅ All tests pass successfully

## Benefits of psycopg3

1. **Better Performance**: Improved query execution and connection handling
2. **Type Safety**: Better Python type hints and PostgreSQL type mapping
3. **Async Support**: Native async/await support (for future use)
4. **Modern API**: Cleaner, more Pythonic API design
5. **Active Development**: psycopg3 is the actively maintained version

## Migration Steps

### For Existing Installations

1. **Update dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify installation**:
   ```bash
   python -c "import psycopg; print(f'psycopg version: {psycopg.__version__}')"
   ```

3. **Run tests**:
   ```bash
   pytest apps/core/tests/
   ```

4. **Check Django configuration**:
   ```bash
   python manage.py check
   ```

### For Docker Deployments

The Docker image will automatically install the correct version. Simply rebuild:

```bash
docker-compose build
docker-compose up -d
```

## Configuration

No configuration changes are required. The existing `DATABASE_URL` format remains the same:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/tulia_db
```

## Rollback (if needed)

If you encounter issues, you can rollback to psycopg2:

```bash
pip uninstall psycopg
pip install psycopg2-binary==2.9.9
```

Then update `requirements.txt` back to the old version.

## Testing

All existing tests pass with psycopg3:

```bash
$ pytest apps/core/tests/ -v
=================== 7 passed in 12.73s ===================
```

## References

- [psycopg3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- [Django psycopg3 Support](https://docs.djangoproject.com/en/4.2/ref/databases/#postgresql-notes)
- [Migration Guide](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html)

## Status

✅ **Migration Complete** - All systems operational with psycopg3
