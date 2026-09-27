import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.categories.models import Category

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_one_user_per_role_and_categories():
    call_command("seed_demo", password="Pass-12345")

    assert set(User.objects.values_list("role", flat=True)) == {Role.ADMIN, Role.OFFICER, Role.CITIZEN}
    assert User.objects.get(email="admin@gsr.local").check_password("Pass-12345")
    assert Category.objects.count() == 5


def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")

    assert User.objects.count() == 3
    assert Category.objects.count() == 5
