import itertools

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

PASSWORD = "S3cure-pass-123"
_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def _isolated_infrastructure(settings):
    """Run without Redis: in-memory cache and Celery tasks executed inline."""
    from config.celery import app as celery_app

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make_user(role=Role.CITIZEN, **kwargs):
        n = next(_seq)
        kwargs.setdefault("email", f"{role.lower()}{n}@example.com")
        kwargs.setdefault("first_name", role.title())
        kwargs.setdefault("last_name", str(n))
        kwargs.setdefault("is_email_verified", True)
        return User.objects.create_user(password=PASSWORD, role=role, **kwargs)

    return _make_user


@pytest.fixture
def citizen(make_user):
    return make_user(Role.CITIZEN)


@pytest.fixture
def officer(make_user):
    return make_user(Role.OFFICER)


@pytest.fixture
def admin_user(make_user):
    return make_user(Role.ADMIN)


@pytest.fixture
def client_for():
    """Returns an APIClient authenticated as the given user."""

    def _client_for(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _client_for


@pytest.fixture
def category(db):
    from apps.categories.models import Category

    return Category.objects.create(name="Water Supply")


@pytest.fixture
def make_request(category):
    from apps.service_requests.models import ServiceRequest

    def _make_request(citizen, **kwargs):
        kwargs.setdefault("category", category)
        kwargs.setdefault("title", "Broken water pipe")
        kwargs.setdefault("description", "The main pipe on Road 5 is leaking.")
        return ServiceRequest.objects.create(citizen=citizen, **kwargs)

    return _make_request
