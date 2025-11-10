"""
Pytest configuration and fixtures.
"""
import pytest
from django.conf import settings
import django
from django.core.management import call_command


def pytest_configure(config):
    """Configure Django settings for tests."""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    django.setup()


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Set up test database with migrations."""
    with django_db_blocker.unblock():
        call_command('migrate', '--run-syncdb', verbosity=0)


@pytest.fixture
def api_client():
    """Return DRF API client."""
    from rest_framework.test import APIClient
    return APIClient()
