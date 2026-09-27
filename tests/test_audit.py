import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.verification import make_token
from apps.audit.models import AuditAction, AuditLog
from apps.categories.models import Category
from apps.service_requests.models import Status
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

URL = reverse("audit-log-list")


def actions():
    return list(AuditLog.objects.order_by("id").values_list("action", flat=True))


def test_successful_and_failed_logins_are_logged(api_client, citizen):
    login_url = reverse("auth-login")
    api_client.post(login_url, {"email": citizen.email, "password": PASSWORD}, format="json")
    api_client.post(login_url, {"email": "ghost@example.com", "password": "nope"}, format="json")

    ok, failed = AuditLog.objects.order_by("id")
    assert ok.action == AuditAction.LOGIN_SUCCEEDED and ok.actor == citizen
    assert ok.ip_address == "127.0.0.1"
    assert failed.action == AuditAction.LOGIN_FAILED and failed.actor is None
    assert failed.changes["email"] == "ghost@example.com"


def test_registration_and_verification_are_logged(api_client, make_user):
    api_client.post(reverse("auth-register"), {"email": "a@b.com", "password": PASSWORD}, format="json")
    user = make_user(is_email_verified=False)
    api_client.get(reverse("auth-verify-email"), {"token": make_token(user)})

    assert actions() == [AuditAction.USER_REGISTERED, AuditAction.EMAIL_VERIFIED]


def test_admin_role_change_records_diff(client_for, admin_user, citizen):
    client_for(admin_user).patch(reverse("user-detail", args=[citizen.pk]), {"role": Role.OFFICER}, format="json")

    entry = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
    assert entry.actor == admin_user
    assert entry.target_type == "user" and entry.target_id == str(citizen.pk)
    assert entry.changes == {"role": {"from": Role.CITIZEN, "to": Role.OFFICER}}


def test_password_values_never_reach_the_log(client_for, admin_user, citizen):
    client_for(admin_user).patch(reverse("user-detail", args=[citizen.pk]), {"password": "N3w-pass-9876"}, format="json")

    entry = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
    assert entry.changes == {"password": "changed"}


def test_request_lifecycle_is_logged(client_for, admin_user, officer, citizen, category):
    citizen_client = client_for(citizen)
    sr_id = citizen_client.post(
        reverse("request-list"), {"category": category.pk, "title": "T", "description": "D"}, format="json"
    ).data["id"]
    citizen_client.patch(reverse("request-detail", args=[sr_id]), {"title": "T2"}, format="json")
    client_for(admin_user).post(reverse("request-assign", args=[sr_id]), {"officer": officer.pk})
    client_for(officer).post(reverse("request-change-status", args=[sr_id]), {"status": Status.IN_PROGRESS})
    client_for(officer).post(reverse("request-comments", args=[sr_id]), {"body": "On it"})

    assert actions() == [
        AuditAction.REQUEST_CREATED,
        AuditAction.REQUEST_UPDATED,
        AuditAction.OFFICER_ASSIGNED,
        AuditAction.REQUEST_STATUS_CHANGED,
        AuditAction.COMMENT_ADDED,
    ]
    status_entry = AuditLog.objects.get(action=AuditAction.REQUEST_STATUS_CHANGED)
    assert status_entry.changes["status"] == {"from": Status.ASSIGNED, "to": Status.IN_PROGRESS}


def test_rejected_actions_are_not_logged(client_for, citizen, make_request):
    sr = make_request(citizen)

    client_for(citizen).post(reverse("request-change-status", args=[sr.pk]), {"status": Status.RESOLVED})

    assert actions() == []


def test_blocked_category_delete_leaves_no_entry(client_for, admin_user, citizen, category, make_request):
    make_request(citizen)

    response = client_for(admin_user).delete(reverse("category-detail", args=[category.pk]))

    assert response.status_code == 409
    assert not AuditLog.objects.filter(action=AuditAction.CATEGORY_DELETED).exists()


def test_category_delete_is_logged(client_for, admin_user):
    category = Category.objects.create(name="Temp")

    client_for(admin_user).delete(reverse("category-detail", args=[category.pk]))

    entry = AuditLog.objects.get(action=AuditAction.CATEGORY_DELETED)
    assert entry.target_id == str(category.pk)
    assert entry.changes == {"name": "Temp"}


def test_admin_can_list_and_filter_audit_logs(client_for, admin_user, citizen):
    client = client_for(admin_user)
    client.patch(reverse("user-detail", args=[citizen.pk]), {"first_name": "X"}, format="json")
    Category.objects.create(name="Other")
    client.post(reverse("category-list"), {"name": "Parks"}, format="json")

    response = client.get(URL, {"action": AuditAction.USER_UPDATED})

    assert response.status_code == 200
    assert [e["action"] for e in response.data["results"]] == [AuditAction.USER_UPDATED]
    assert response.data["results"][0]["actor_email"] == admin_user.email


def test_audit_log_is_read_only_and_admin_only(client_for, admin_user, citizen, officer):
    assert client_for(admin_user).post(URL, {}).status_code == 405
    assert client_for(citizen).get(URL).status_code == 403
    assert client_for(officer).get(URL).status_code == 403
