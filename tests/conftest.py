import itertools

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

PASSWORD = "S3cure-pass-123"
_seq = itertools.count(1)


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
