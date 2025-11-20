# Soft Delete Field Fix - Summary

## Issue
Migration `0018_fix_provider_tracking_soft_delete.py` was created to fix soft delete fields in provider tracking models, but several issues were discovered:

1. **Incorrect field usage**: Code was querying `is_deleted=False` which doesn't work because `is_deleted` is a property, not a database field in BaseModel
2. **Incomplete migrations**: Models were created with `BigAutoField` and `is_deleted` boolean instead of `UUIDField` and `deleted_at` timestamp
3. **Missing model imports**: Provider tracking and feedback models weren't imported in `apps/bot/models.py`

## Root Cause
The original migrations (0015 for provider tracking, 0016 for feedback) created models with incorrect field types that didn't match the BaseModel pattern used throughout WabotIQ.

## BaseModel Soft Delete Pattern
```python
# BaseModel uses:
- deleted_at: DateTimeField (timestamp when deleted, NULL = not deleted)
- objects: Manager that automatically filters deleted_at__isnull=True
- objects_with_deleted: Manager that includes soft-deleted records
- is_deleted: Property (not a field!) that returns deleted_at is not None

# WRONG:
Model.objects.filter(is_deleted=False)  # ❌ is_deleted is not a field!

# CORRECT:
Model.objects.all()  # ✅ Default manager excludes soft-deleted
Model.objects_with_deleted.filter(deleted_at__isnull=True)  # ✅ Explicit
```

## Changes Made

### 1. Fixed Code References (5 files)
Removed all `is_deleted=False` filters since the default `objects` manager already excludes soft-deleted records:

- **apps/bot/services/ai_agent_service.py**: Removed `is_deleted=False` from AgentInteraction query
- **apps/bot/views_feedback.py**: Fixed 4 queries (InteractionFeedback and HumanCorrection)
- **apps/bot/serializers_feedback.py**: Fixed AgentInteraction validation query
- **apps/bot/tasks_provider_tracking.py**: Fixed 3 queries and 1 update operation

### 2. Created Proper Migrations (3 new migrations)

#### Migration 0019: Fix Provider Tracking Models
- Dropped incorrectly created `ProviderUsage` and `ProviderDailySummary` tables
- Recreated with correct BaseModel fields:
  - `id`: UUIDField (not BigAutoField)
  - `deleted_at`: DateTimeField (not is_deleted boolean)
  - Proper indexes and relationships

#### Migration 0020: Fix Feedback Models
- Dropped incorrectly created `InteractionFeedback` and `HumanCorrection` tables
- Recreated with correct BaseModel fields
- Added missing fields: `metadata` and `quality_score`
- Proper indexes and relationships

#### Migration 0021: Index Cleanup
- Django auto-generated migration to normalize index names
- No functional changes, just cosmetic cleanup

### 3. Fixed Custom Managers (4 managers)
Custom managers must inherit from `BaseModelManager` to get soft delete filtering:

- **apps/bot/models_provider_tracking.py**:
  - `ProviderUsageManager(BaseModelManager)` - was `models.Manager`
  - `ProviderDailySummaryManager(BaseModelManager)` - was `models.Manager`

- **apps/bot/models_feedback.py**:
  - `InteractionFeedbackManager(BaseModelManager)` - was `models.Manager`
  - `HumanCorrectionManager(BaseModelManager)` - was `models.Manager`

This ensures the default `objects` manager automatically filters out soft-deleted records.

### 4. Fixed Model Imports
Added imports to `apps/bot/models.py`:
```python
# Import provider tracking models
from apps.bot.models_provider_tracking import (
    ProviderUsage,
    ProviderDailySummary
)

# Import feedback models
from apps.bot.models_feedback import (
    InteractionFeedback,
    HumanCorrection
)
```

Updated `__all__` export list to include these models.

## Verification

### No Data Loss
Confirmed zero records in all affected tables before migration:
```bash
ProviderUsage count: 0
ProviderDailySummary count: 0
InteractionFeedback count: 0
HumanCorrection count: 0
```

### Migrations Applied Successfully
```bash
✓ Migration 0018: fix_provider_tracking_soft_delete
✓ Migration 0019: fix_provider_tracking_basemodel
✓ Migration 0020: fix_feedback_models_basemodel
✓ Migration 0021: index cleanup
✓ No pending migrations detected
```

### Models Import Correctly
```bash
✓ All models imported successfully
✓ ProviderUsage table: bot_provider_usage
✓ ProviderDailySummary table: bot_provider_daily_summary
✓ InteractionFeedback table: bot_interaction_feedback
✓ HumanCorrection table: bot_human_correction
```

## Files Modified

### Code Files (7)
1. `apps/bot/services/ai_agent_service.py` - Removed is_deleted filter
2. `apps/bot/views_feedback.py` - Fixed 4 queries
3. `apps/bot/serializers_feedback.py` - Fixed validation query
4. `apps/bot/tasks_provider_tracking.py` - Fixed 3 queries + 1 update
5. `apps/bot/models.py` - Added model imports
6. `apps/bot/models_provider_tracking.py` - Fixed 2 managers to inherit from BaseModelManager
7. `apps/bot/models_feedback.py` - Fixed 2 managers to inherit from BaseModelManager

### Migration Files (4)
1. `apps/bot/migrations/0018_fix_provider_tracking_soft_delete.py` - Updated with operations
2. `apps/bot/migrations/0019_fix_provider_tracking_basemodel.py` - New
3. `apps/bot/migrations/0020_fix_feedback_models_basemodel.py` - New
4. `apps/bot/migrations/0021_rename_indexes.py` - Auto-generated

## Testing

### Manual Verification
```bash
# Verify no is_deleted field references remain
grep -r "is_deleted=" apps/bot/**/*.py --exclude-dir=migrations
# Result: No matches (✓)

# Verify models use BaseModel correctly
python manage.py shell -c "from apps.bot.models_provider_tracking import ProviderUsage; print(hasattr(ProviderUsage, 'deleted_at'))"
# Result: True (✓)

# Verify managers inherit from BaseModelManager
python manage.py shell -c "from apps.bot.models import ProviderUsage; from apps.core.models import BaseModelManager; print(isinstance(ProviderUsage.objects, BaseModelManager))"
# Result: True (✓)

# Test soft delete functionality
python manage.py shell -c "
from apps.bot.models import ProviderUsage
from apps.tenants.models import Tenant
tenant = Tenant.objects.first()
usage = ProviderUsage.objects.create(tenant=tenant, provider='test', model='test', input_tokens=1, output_tokens=1, total_tokens=2, estimated_cost=0, latency_ms=1)
print('Before delete:', ProviderUsage.objects.count())  # 1
usage.delete()
print('After soft delete:', ProviderUsage.objects.count())  # 0
print('With deleted:', ProviderUsage.objects_with_deleted.count())  # 1
usage.hard_delete()
"
# Result: Soft delete works correctly (✓)
```

## Best Practices Enforced

1. **Always use BaseModel**: All models inherit from BaseModel for consistent soft delete behavior
2. **Use default manager**: `Model.objects.all()` automatically excludes soft-deleted records
3. **Explicit when needed**: Use `Model.objects_with_deleted` when you need to include deleted records
4. **Soft delete updates**: Use `update(deleted_at=timezone.now())` not `update(is_deleted=True)`
5. **Import models properly**: Ensure all models are imported in the app's main `models.py`

## Impact

- **Zero data loss**: No existing data affected (all tables were empty)
- **Zero downtime**: Migrations run in milliseconds
- **Improved consistency**: All models now follow the same soft delete pattern
- **Better performance**: Default manager filtering is more efficient than explicit is_deleted checks
- **Cleaner code**: Removed redundant `is_deleted=False` filters throughout codebase

## Related Documentation

- BaseModel implementation: `apps/core/models.py`
- Soft delete pattern: WabotIQ uses timestamp-based soft deletes (deleted_at) not boolean flags
- Manager behavior: Default manager excludes soft-deleted, use objects_with_deleted to include them

---

**Status**: ✅ Complete
**Date**: 2025-11-20
**Agent**: BotAgent
**Migrations Applied**: 0018, 0019, 0020, 0021
**Files Modified**: 11 (7 code files, 4 migrations)
**Tests**: All passing
**Soft Delete**: ✅ Verified working correctly
