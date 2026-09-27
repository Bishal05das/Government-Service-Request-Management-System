import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.throttling import SimpleRateThrottle

from apps.service_requests.models import Status
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def rates(monkeypatch):
    """Throttle rates are read once at import; patch the class-level dict per test."""

    def _set(**overrides):
        monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", {**SimpleRateThrottle.THROTTLE_RATES, **overrides})

    return _set


def test_login_is_throttled_per_ip(api_client, citizen, rates):
    rates(login="3/minute")
    url = reverse("auth-login")
    payload = {"email": citizen.email, "password": "wrong"}

    codes = [api_client.post(url, payload, format="json").status_code for _ in range(4)]

    assert codes == [401, 401, 401, 429]
    assert "Retry-After" in api_client.post(url, payload, format="json")


def test_spoofed_forwarded_for_does_not_reset_the_limit(api_client, citizen, rates):
    rates(login="2/minute")
    url = reverse("auth-login")
    payload = {"email": citizen.email, "password": "wrong"}

    codes = [
        api_client.post(url, payload, format="json", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}").status_code
        for i in range(3)
    ]

    assert codes[-1] == 429


def test_register_is_throttled(api_client, rates):
    rates(register="2/hour")
    url = reverse("auth-register")

    codes = [
        api_client.post(url, {"email": f"u{i}@example.com", "password": PASSWORD}, format="json").status_code
        for i in range(3)
    ]

    assert codes == [201, 201, 429]


def test_resend_verification_is_throttled(api_client, rates):
    rates(email="1/hour")
    url = reverse("auth-resend-verification")

    first = api_client.post(url, {"email": "a@example.com"}, format="json")
    second = api_client.post(url, {"email": "b@example.com"}, format="json")

    assert (first.status_code, second.status_code) == (200, 429)


def test_authenticated_users_have_their_own_budget(client_for, citizen, make_user, rates):
    rates(user="2/minute")
    url = reverse("auth-me")
    client = client_for(citizen)

    assert [client.get(url).status_code for _ in range(3)] == [200, 200, 429]
    assert client_for(make_user()).get(url).status_code == 200


def test_uploads_have_a_separate_budget(settings, tmp_path, client_for, citizen, officer, make_request, rates):
    settings.MEDIA_ROOT = tmp_path
    rates(uploads="1/hour")
    sr = make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)
    client = client_for(citizen)
    url = reverse("request-attachments", args=[sr.pk])

    def upload():
        return client.post(url, {"file": SimpleUploadedFile("a.txt", b"x")}, format="multipart")

    assert upload().status_code == 201
    assert upload().status_code == 429
    assert client.get(url).status_code == 200  # listing is not limited by the upload budget
