# CRITICAL: Virtual Environment

## Always Activate Virtual Environment First!

Before running ANY Python commands in this project, ALWAYS activate the virtual environment:

```bash
source venv/bin/activate
```

## Why This Matters
- Without activation, `python` command won't be found
- Need to use `python3` explicitly without venv
- Dependencies won't be available
- Tests will fail or behave unexpectedly

## Correct Command Pattern
```bash
# WRONG (without venv)
python manage.py migrate
python -m pytest

# RIGHT (with venv activated)
source venv/bin/activate
python manage.py migrate
python -m pytest
```

## Quick Check
If you see `(venv)` in the terminal prompt, you're good to go!
