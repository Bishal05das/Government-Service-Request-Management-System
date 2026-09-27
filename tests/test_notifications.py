import pytest
from django.urls import reverse

from apps.service_requests.models import Status

pytestmark = pytest.mark.django_db


@pytest.fixture
def capture(django_capture_on_commit_callbacks):
    """Run on-commit callbacks (where emails are queued) as the test's transaction never commits."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def recipients(mailoutbox):
    return sorted(address for message in mailoutbox for address in message.to)


def test_assignment_notifies_officer_and_citizen(client_for, admin_user, officer, citizen, make_request,
                                                  mailoutbox, capture):
    sr = make_request(citizen)

    with capture():
        client_for(admin_user).post(reverse("request-assign", args=[sr.pk]), {"officer": officer.pk})

    assert recipients(mailoutbox) == sorted([officer.email, citizen.email])
    assert all(f"[Request #{sr.pk}]" in m.subject for m in mailoutbox)


def test_status_change_notifies_everyone_but_the_actor(client_for, officer, citizen, make_request,
                                                       mailoutbox, capture):
    sr = make_request(citizen, status=Status.IN_PROGRESS, assigned_officer=officer)

    with capture():
        client_for(officer).post(
            reverse("request-change-status", args=[sr.pk]), {"status": Status.RESOLVED, "note": "Fixed"}
        )

    assert recipients(mailoutbox) == [citizen.email]
    assert "Fixed" in mailoutbox[0].body


def test_citizen_closing_notifies_officer(client_for, officer, citizen, make_request, mailoutbox, capture):
    sr = make_request(citizen, status=Status.RESOLVED, assigned_officer=officer)

    with capture():
        client_for(citizen).post(reverse("request-change-status", args=[sr.pk]), {"status": Status.CLOSED})

    assert recipients(mailoutbox) == [officer.email]


def test_comment_notifies_the_other_party(client_for, officer, citizen, make_request, mailoutbox, capture):
    sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)

    with capture():
        client_for(citizen).post(reverse("request-comments", args=[sr.pk]), {"body": "Any update?"})

    assert recipients(mailoutbox) == [officer.email]
    assert "Any update?" in mailoutbox[0].body


def test_failed_transition_sends_nothing(client_for, citizen, make_request, mailoutbox, capture):
    sr = make_request(citizen)

    with capture():
        client_for(citizen).post(reverse("request-change-status", args=[sr.pk]), {"status": Status.RESOLVED})

    assert mailoutbox == []
