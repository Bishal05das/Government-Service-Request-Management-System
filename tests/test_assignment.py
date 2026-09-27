import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.service_requests.models import Status

pytestmark = pytest.mark.django_db


def assign_url(pk):
    return reverse("request-assign", args=[pk])


def test_admin_assigns_officer_to_submitted_request(client_for, admin_user, officer, citizen, make_request):
    sr = make_request(citizen)

    response = client_for(admin_user).post(assign_url(sr.pk), {"officer": officer.pk})

    assert response.status_code == 200
    assert response.data["status"] == Status.ASSIGNED
    assert response.data["assigned_officer"]["id"] == officer.pk
    assert response.data["assigned_at"] is not None
    assert response.data["status_history"][-1]["to_status"] == Status.ASSIGNED


def test_assigned_officer_can_then_see_and_start_the_request(client_for, admin_user, officer, citizen, make_request):
    sr = make_request(citizen)
    client_for(admin_user).post(assign_url(sr.pk), {"officer": officer.pk})

    response = client_for(officer).get(reverse("request-detail", args=[sr.pk]))

    assert response.status_code == 200
    assert response.data["allowed_transitions"] == [Status.IN_PROGRESS, Status.REJECTED]


def test_reassignment_keeps_in_progress_status(client_for, admin_user, officer, make_user, citizen, make_request):
    sr = make_request(citizen, status=Status.IN_PROGRESS, assigned_officer=officer)
    other = make_user(Role.OFFICER)

    response = client_for(admin_user).post(assign_url(sr.pk), {"officer": other.pk})

    assert response.status_code == 200
    assert response.data["status"] == Status.IN_PROGRESS
    assert response.data["assigned_officer"]["id"] == other.pk
    assert client_for(officer).get(reverse("request-detail", args=[sr.pk])).status_code == 404


@pytest.mark.parametrize("status", [Status.RESOLVED, Status.CLOSED, Status.REJECTED, Status.CANCELLED])
def test_cannot_assign_finished_request(client_for, admin_user, officer, citizen, make_request, status):
    sr = make_request(citizen, status=status)

    assert client_for(admin_user).post(assign_url(sr.pk), {"officer": officer.pk}).status_code == 400


def test_only_active_officers_can_be_assigned(client_for, admin_user, citizen, make_user, make_request):
    sr = make_request(citizen)
    client = client_for(admin_user)
    inactive = make_user(Role.OFFICER, is_active=False)

    assert client.post(assign_url(sr.pk), {"officer": citizen.pk}).status_code == 400
    assert client.post(assign_url(sr.pk), {"officer": inactive.pk}).status_code == 400


@pytest.mark.parametrize("role_fixture", ["citizen", "officer"])
def test_non_admins_cannot_assign(request, client_for, officer, citizen, make_request, role_fixture):
    sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)
    user = request.getfixturevalue(role_fixture)

    assert client_for(user).post(assign_url(sr.pk), {"officer": officer.pk}).status_code == 403
