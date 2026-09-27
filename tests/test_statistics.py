from datetime import timedelta

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.categories.models import Category
from apps.service_requests.models import Priority, ServiceRequest, Status

pytestmark = pytest.mark.django_db

URL = reverse("admin-statistics")


def test_statistics_summarise_requests(client_for, admin_user, citizen, officer, category, make_request):
    roads = Category.objects.create(name="Roads")
    make_request(citizen, priority=Priority.URGENT)
    make_request(citizen, status=Status.IN_PROGRESS, assigned_officer=officer)
    resolved = make_request(citizen, category=roads, status=Status.RESOLVED, assigned_officer=officer)
    ServiceRequest.objects.filter(pk=resolved.pk).update(
        resolved_at=resolved.created_at + timedelta(hours=5)
    )

    data = client_for(admin_user).get(URL).json()

    assert data["requests"]["total"] == 3
    assert data["requests"]["open"] == 2
    assert data["requests"]["unassigned"] == 1
    assert data["requests"]["created_last_7_days"] == 3
    assert data["requests"]["by_status"][Status.SUBMITTED] == 1
    assert data["requests"]["by_status"][Status.CLOSED] == 0
    assert data["requests"]["by_priority"][Priority.URGENT] == 1
    assert data["requests"]["average_resolution_hours"] == 5.0

    assert data["by_category"] == [
        {"id": category.pk, "name": "Water Supply", "total": 2, "open": 2},
        {"id": roads.pk, "name": "Roads", "total": 1, "open": 0},
    ]
    assert data["officer_workload"] == [
        {"id": officer.pk, "email": officer.email, "is_active": True, "open": 1, "resolved": 1},
    ]
    assert data["users_by_role"] == {Role.CITIZEN: 1, Role.OFFICER: 1, Role.ADMIN: 1}


def test_statistics_with_no_data(client_for, admin_user):
    data = client_for(admin_user).get(URL).json()

    assert data["requests"]["total"] == 0
    assert data["requests"]["average_resolution_hours"] is None


@pytest.mark.parametrize("role", [Role.CITIZEN, Role.OFFICER])
def test_statistics_are_admin_only(client_for, make_user, role):
    assert client_for(make_user(role)).get(URL).status_code == 403
