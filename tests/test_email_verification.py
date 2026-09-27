import re

import pytest
from django.core import signing
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.verification import SALT, make_token
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def register(client, email="new@example.com"):
    return client.post(
        reverse("auth-register"),
        {"email": email, "password": PASSWORD, "first_name": "New"},
        format="json",
    )


def login(client, email):
    return client.post(reverse("auth-login"), {"email": email, "password": PASSWORD}, format="json")


def token_from(message):
    return re.search(r"token=(\S+)", message.body).group(1)


def test_registration_sends_verification_email(api_client, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = register(api_client)

    assert response.status_code == 201
    assert response.data["email"] == "new@example.com"
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["new@example.com"]
    assert "/api/v1/auth/verify-email/?token=" in mailoutbox[0].body


def test_unverified_user_cannot_log_in(api_client):
    register(api_client)

    response = login(api_client, "new@example.com")

    assert response.status_code == 401
    assert response.data["detail"].code == "email_not_verified"


def test_wrong_password_does_not_reveal_verification_state(api_client):
    register(api_client)

    response = api_client.post(
        reverse("auth-login"), {"email": "new@example.com", "password": "wrong"}, format="json"
    )

    assert response.status_code == 401
    assert response.data["detail"].code != "email_not_verified"


def test_verification_link_activates_login(api_client, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        register(api_client)

    verify = api_client.get(reverse("auth-verify-email"), {"token": token_from(mailoutbox[0])})

    assert verify.status_code == 200
    assert User.objects.get(email="new@example.com").is_email_verified
    assert login(api_client, "new@example.com").status_code == 200


def test_verification_via_post_body(api_client, make_user):
    user = make_user(is_email_verified=False)

    response = api_client.post(reverse("auth-verify-email"), {"token": make_token(user)}, format="json")

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.is_email_verified


def test_tampered_token_is_rejected(api_client, make_user):
    user = make_user(is_email_verified=False)

    response = api_client.get(reverse("auth-verify-email"), {"token": make_token(user) + "x"})

    assert response.status_code == 400


def test_expired_token_is_rejected(api_client, make_user, settings):
    user = make_user(is_email_verified=False)
    settings.EMAIL_VERIFICATION_TOKEN_HOURS = -1

    response = api_client.get(reverse("auth-verify-email"), {"token": make_token(user)})

    assert response.status_code == 400


def test_token_stops_working_after_email_change(api_client, make_user):
    user = make_user(is_email_verified=False)
    token = signing.dumps({"uid": user.pk, "email": "old@example.com"}, salt=SALT)

    assert api_client.get(reverse("auth-verify-email"), {"token": token}).status_code == 400


def test_resend_sends_new_link_only_for_unverified_accounts(
    api_client, make_user, mailoutbox, django_capture_on_commit_callbacks
):
    unverified = make_user(is_email_verified=False)
    verified = make_user()
    url = reverse("auth-resend-verification")

    with django_capture_on_commit_callbacks(execute=True):
        responses = [
            api_client.post(url, {"email": unverified.email}, format="json"),
            api_client.post(url, {"email": verified.email}, format="json"),
            api_client.post(url, {"email": "nobody@example.com"}, format="json"),
        ]

    assert {r.status_code for r in responses} == {200}
    assert len({r.data["detail"] for r in responses}) == 1  # identical answers
    assert [m.to for m in mailoutbox] == [[unverified.email]]


def test_admin_created_accounts_are_verified(client_for, admin_user):
    client_for(admin_user).post(
        reverse("user-list"), {"email": "off@gov.test", "password": PASSWORD, "role": Role.OFFICER}, format="json"
    )

    assert User.objects.get(email="off@gov.test").is_email_verified


def test_verification_can_be_disabled(api_client, settings):
    settings.EMAIL_VERIFICATION_REQUIRED = False
    register(api_client)

    assert login(api_client, "new@example.com").status_code == 200
