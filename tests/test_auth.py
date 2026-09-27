import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Role, User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def register(client, **overrides):
    payload = {"email": "Jane@Example.com", "password": PASSWORD, "first_name": "Jane", "last_name": "Doe"}
    payload.update(overrides)
    return client.post(reverse("auth-register"), payload, format="json")


def login(client, email, password=PASSWORD):
    return client.post(reverse("auth-login"), {"email": email, "password": password}, format="json")


class TestRegistration:
    def test_register_creates_citizen(self, api_client):
        response = register(api_client)

        assert response.status_code == 201
        assert response.data["role"] == Role.CITIZEN
        assert response.data["email"] == "jane@example.com"
        assert "password" not in response.data

    def test_role_cannot_be_chosen_on_register(self, api_client):
        response = register(api_client, role=Role.ADMIN)

        assert response.status_code == 201
        assert User.objects.get(email="jane@example.com").role == Role.CITIZEN

    def test_duplicate_email_is_rejected_case_insensitively(self, api_client):
        register(api_client)
        response = register(api_client, email="JANE@example.com")

        assert response.status_code == 400
        assert "email" in response.data

    def test_weak_password_is_rejected(self, api_client):
        response = register(api_client, password="123")

        assert response.status_code == 400


class TestLogin:
    def test_login_returns_token_pair_with_role_claim(self, api_client, officer):
        response = login(api_client, officer.email.upper())

        assert response.status_code == 200
        assert {"access", "refresh"} <= response.data.keys()

        assert AccessToken(response.data["access"])["role"] == Role.OFFICER

    def test_wrong_password_is_rejected(self, api_client, citizen):
        assert login(api_client, citizen.email, "wrong").status_code == 401

    def test_access_token_authenticates_requests(self, api_client, citizen):
        access = login(api_client, citizen.email).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = api_client.get(reverse("auth-me"))

        assert response.status_code == 200
        assert response.data["email"] == citizen.email

    def test_protected_endpoint_requires_token(self, api_client):
        assert api_client.get(reverse("auth-me")).status_code == 401

    def test_logout_blacklists_refresh_token(self, api_client, citizen):
        tokens = login(api_client, citizen.email).data
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        assert api_client.post(reverse("auth-logout"), {"refresh": tokens["refresh"]}).status_code == 205
        refresh = api_client.post(reverse("auth-refresh"), {"refresh": tokens["refresh"]})
        assert refresh.status_code == 401


class TestProfile:
    def test_user_can_update_name_but_not_role(self, client_for, citizen):
        response = client_for(citizen).patch(
            reverse("auth-me"), {"first_name": "New", "role": Role.ADMIN}, format="json"
        )

        citizen.refresh_from_db()
        assert response.status_code == 200
        assert citizen.first_name == "New"
        assert citizen.role == Role.CITIZEN


class TestUserManagement:
    def test_admin_can_create_officer(self, client_for, admin_user):
        response = client_for(admin_user).post(
            reverse("user-list"),
            {"email": "officer@gov.test", "password": PASSWORD, "role": Role.OFFICER},
            format="json",
        )

        assert response.status_code == 201
        officer = User.objects.get(email="officer@gov.test")
        assert officer.role == Role.OFFICER
        assert officer.check_password(PASSWORD)

    def test_admin_can_change_role_and_deactivate(self, client_for, admin_user, citizen):
        response = client_for(admin_user).patch(
            reverse("user-detail", args=[citizen.pk]),
            {"role": Role.OFFICER, "is_active": False},
            format="json",
        )

        citizen.refresh_from_db()
        assert response.status_code == 200
        assert citizen.role == Role.OFFICER
        assert citizen.is_active is False

    def test_admin_cannot_demote_self(self, client_for, admin_user):
        response = client_for(admin_user).patch(
            reverse("user-detail", args=[admin_user.pk]), {"role": Role.CITIZEN}, format="json"
        )

        assert response.status_code == 400

    def test_admin_can_filter_users_by_role(self, client_for, admin_user, officer, citizen):
        response = client_for(admin_user).get(reverse("user-list"), {"role": Role.OFFICER})

        assert [u["id"] for u in response.data["results"]] == [officer.pk]

    @pytest.mark.parametrize("role", [Role.CITIZEN, Role.OFFICER])
    def test_non_admins_cannot_manage_users(self, client_for, make_user, role):
        response = client_for(make_user(role)).get(reverse("user-list"))

        assert response.status_code == 403

    def test_users_cannot_be_deleted(self, client_for, admin_user, citizen):
        response = client_for(admin_user).delete(reverse("user-detail", args=[citizen.pk]))

        assert response.status_code == 405
