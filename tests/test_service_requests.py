import pytest
from django.urls import reverse

from apps.categories.models import Category
from apps.service_requests.models import Priority, ServiceRequest, Status

pytestmark = pytest.mark.django_db

LIST_URL = reverse("request-list")


def detail_url(pk):
    return reverse("request-detail", args=[pk])


def status_url(pk):
    return reverse("request-change-status", args=[pk])


class TestCreate:
    def test_citizen_submits_request(self, client_for, citizen, category):
        response = client_for(citizen).post(
            LIST_URL,
            {"category": category.pk, "title": "Pothole", "description": "Deep pothole", "priority": Priority.HIGH},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["status"] == Status.SUBMITTED
        assert response.data["citizen"]["id"] == citizen.pk
        request = ServiceRequest.objects.get()
        assert request.status_history.get().to_status == Status.SUBMITTED

    def test_priority_defaults_to_medium(self, client_for, citizen, category):
        response = client_for(citizen).post(
            LIST_URL, {"category": category.pk, "title": "T", "description": "D"}, format="json"
        )

        assert response.data["priority"] == Priority.MEDIUM

    def test_status_and_officer_cannot_be_set_on_create(self, client_for, citizen, officer, category):
        response = client_for(citizen).post(
            LIST_URL,
            {"category": category.pk, "title": "T", "description": "D",
             "status": Status.RESOLVED, "assigned_officer": officer.pk},
            format="json",
        )

        assert response.data["status"] == Status.SUBMITTED
        assert response.data["assigned_officer"] is None

    def test_inactive_category_is_rejected(self, client_for, citizen):
        closed = Category.objects.create(name="Closed", is_active=False)

        response = client_for(citizen).post(
            LIST_URL, {"category": closed.pk, "title": "T", "description": "D"}, format="json"
        )

        assert response.status_code == 400
        assert "category" in response.data

    @pytest.mark.parametrize("role_fixture", ["officer", "admin_user"])
    def test_only_citizens_can_submit(self, request, client_for, category, role_fixture):
        user = request.getfixturevalue(role_fixture)

        response = client_for(user).post(
            LIST_URL, {"category": category.pk, "title": "T", "description": "D"}, format="json"
        )

        assert response.status_code == 403


class TestVisibility:
    def test_citizen_sees_only_own_requests(self, client_for, citizen, make_user, make_request):
        own = make_request(citizen)
        make_request(make_user())

        response = client_for(citizen).get(LIST_URL)

        assert [r["id"] for r in response.data["results"]] == [own.pk]

    def test_citizen_cannot_view_others_request(self, client_for, citizen, make_user, make_request):
        other = make_request(make_user())

        assert client_for(citizen).get(detail_url(other.pk)).status_code == 404

    def test_officer_sees_only_assigned_requests(self, client_for, citizen, officer, make_request):
        mine = make_request(citizen, assigned_officer=officer, status=Status.ASSIGNED)
        make_request(citizen)

        response = client_for(officer).get(LIST_URL)

        assert [r["id"] for r in response.data["results"]] == [mine.pk]

    def test_admin_sees_all_requests(self, client_for, admin_user, citizen, make_user, make_request):
        make_request(citizen)
        make_request(make_user())

        assert client_for(admin_user).get(LIST_URL).data["count"] == 2

    def test_list_can_be_filtered_and_ordered_by_priority(self, client_for, admin_user, citizen, make_request):
        low = make_request(citizen, priority=Priority.LOW)
        urgent = make_request(citizen, priority=Priority.URGENT)
        make_request(citizen, status=Status.CANCELLED)
        client = client_for(admin_user)

        ordered = client.get(LIST_URL, {"status": Status.SUBMITTED, "ordering": "-priority_rank"})

        assert [r["id"] for r in ordered.data["results"]] == [urgent.pk, low.pk]

    def test_detail_includes_history_and_allowed_transitions(self, client_for, citizen, make_request):
        sr = make_request(citizen)

        response = client_for(citizen).get(detail_url(sr.pk))

        assert response.data["allowed_transitions"] == [Status.CANCELLED]
        assert "status_history" in response.data


class TestUpdate:
    def test_owner_can_edit_while_submitted(self, client_for, citizen, make_request):
        sr = make_request(citizen)

        response = client_for(citizen).patch(detail_url(sr.pk), {"title": "Updated"}, format="json")

        assert response.status_code == 200
        assert response.data["title"] == "Updated"

    def test_owner_cannot_edit_after_assignment(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)

        response = client_for(citizen).patch(detail_url(sr.pk), {"title": "Updated"}, format="json")

        assert response.status_code == 403

    def test_officer_cannot_edit_details(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)

        response = client_for(officer).patch(detail_url(sr.pk), {"priority": Priority.LOW}, format="json")

        assert response.status_code == 403

    def test_admin_can_edit_open_request_but_not_closed(self, client_for, admin_user, citizen, make_request):
        open_request = make_request(citizen, status=Status.IN_PROGRESS)
        closed = make_request(citizen, status=Status.CLOSED)
        client = client_for(admin_user)

        assert client.patch(detail_url(open_request.pk), {"priority": Priority.URGENT}, format="json").status_code == 200
        assert client.patch(detail_url(closed.pk), {"priority": Priority.URGENT}, format="json").status_code == 403

    def test_status_is_read_only_on_patch(self, client_for, citizen, make_request):
        sr = make_request(citizen)

        client_for(citizen).patch(detail_url(sr.pk), {"status": Status.CLOSED}, format="json")

        sr.refresh_from_db()
        assert sr.status == Status.SUBMITTED

    def test_requests_cannot_be_deleted(self, client_for, admin_user, citizen, make_request):
        sr = make_request(citizen)

        assert client_for(admin_user).delete(detail_url(sr.pk)).status_code == 405


class TestWorkflow:
    def test_full_happy_path(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)
        officer_client, citizen_client = client_for(officer), client_for(citizen)

        assert officer_client.post(status_url(sr.pk), {"status": Status.IN_PROGRESS}).status_code == 200
        resolved = officer_client.post(status_url(sr.pk), {"status": Status.RESOLVED, "note": "Pipe replaced"})
        assert resolved.status_code == 200
        assert resolved.data["resolved_at"] is not None
        assert citizen_client.post(status_url(sr.pk), {"status": Status.CLOSED}).status_code == 200

        sr.refresh_from_db()
        assert sr.status == Status.CLOSED
        assert list(sr.status_history.values_list("to_status", flat=True)) == [
            Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED,
        ]

    def test_owner_can_cancel_submitted_request(self, client_for, citizen, make_request):
        sr = make_request(citizen)

        response = client_for(citizen).post(status_url(sr.pk), {"status": Status.CANCELLED})

        assert response.status_code == 200
        assert response.data["status"] == Status.CANCELLED

    def test_owner_cannot_cancel_after_assignment(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)

        response = client_for(citizen).post(status_url(sr.pk), {"status": Status.CANCELLED})

        assert response.status_code == 400

    def test_invalid_transition_is_rejected(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)

        response = client_for(officer).post(status_url(sr.pk), {"status": Status.CLOSED})

        assert response.status_code == 400

    def test_submitted_cannot_be_moved_to_assigned_via_status(self, client_for, admin_user, citizen, make_request):
        sr = make_request(citizen)

        response = client_for(admin_user).post(status_url(sr.pk), {"status": Status.ASSIGNED})

        assert response.status_code == 400

    def test_citizen_cannot_resolve(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.IN_PROGRESS, assigned_officer=officer)

        response = client_for(citizen).post(status_url(sr.pk), {"status": Status.RESOLVED})

        assert response.status_code == 403

    def test_rejection_requires_note(self, client_for, citizen, officer, make_request):
        sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)
        client = client_for(officer)

        assert client.post(status_url(sr.pk), {"status": Status.REJECTED}).status_code == 400
        response = client.post(status_url(sr.pk), {"status": Status.REJECTED, "note": "Out of jurisdiction"})
        assert response.status_code == 200
        assert response.data["status_history"][-1]["note"] == "Out of jurisdiction"

    def test_admin_can_close_resolved_request(self, client_for, admin_user, citizen, make_request):
        sr = make_request(citizen, status=Status.RESOLVED)

        assert client_for(admin_user).post(status_url(sr.pk), {"status": Status.CLOSED}).status_code == 200
