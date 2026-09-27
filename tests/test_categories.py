import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.categories.models import Category

pytestmark = pytest.mark.django_db

LIST_URL = reverse("category-list")


def detail_url(pk):
    return reverse("category-detail", args=[pk])


@pytest.fixture
def water():
    return Category.objects.create(name="Water Supply")


@pytest.fixture
def retired():
    return Category.objects.create(name="Retired Service", is_active=False)


def test_admin_can_create_category(client_for, admin_user):
    response = client_for(admin_user).post(LIST_URL, {"name": "Road Maintenance"}, format="json")

    assert response.status_code == 201
    assert Category.objects.filter(name="Road Maintenance").exists()


def test_category_names_are_unique_case_insensitively(client_for, admin_user, water):
    response = client_for(admin_user).post(LIST_URL, {"name": "water supply"}, format="json")

    assert response.status_code == 400


def test_admin_can_update_and_delete_category(client_for, admin_user, water):
    client = client_for(admin_user)

    assert client.patch(detail_url(water.pk), {"is_active": False}, format="json").status_code == 200
    assert client.delete(detail_url(water.pk)).status_code == 204
    assert not Category.objects.exists()


@pytest.mark.parametrize("role", [Role.CITIZEN, Role.OFFICER])
def test_non_admin_cannot_write_categories(client_for, make_user, water, role):
    client = client_for(make_user(role))

    assert client.post(LIST_URL, {"name": "New"}, format="json").status_code == 403
    assert client.patch(detail_url(water.pk), {"name": "X"}, format="json").status_code == 403
    assert client.delete(detail_url(water.pk)).status_code == 403


def test_non_admin_only_sees_active_categories(client_for, citizen, water, retired):
    response = client_for(citizen).get(LIST_URL)

    assert [c["name"] for c in response.data["results"]] == ["Water Supply"]


def test_admin_sees_all_categories(client_for, admin_user, water, retired):
    response = client_for(admin_user).get(LIST_URL)

    assert response.data["count"] == 2


def test_anonymous_cannot_list_categories(api_client):
    assert api_client.get(LIST_URL).status_code == 401
