import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.service_requests.models import Comment, Status

pytestmark = pytest.mark.django_db


def comments_url(pk):
    return reverse("request-comments", args=[pk])


@pytest.fixture
def assigned_request(citizen, officer, make_request):
    return make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)


def test_owner_officer_and_admin_can_comment(client_for, citizen, officer, admin_user, assigned_request):
    for user in (citizen, officer, admin_user):
        response = client_for(user).post(comments_url(assigned_request.pk), {"body": f"Hi from {user.role}"})
        assert response.status_code == 201
        assert response.data["author"]["id"] == user.pk
        assert response.data["author_role"] == user.role

    assert assigned_request.comments.count() == 3


def test_comments_are_listed_oldest_first(client_for, citizen, officer, assigned_request):
    Comment.objects.create(service_request=assigned_request, author=citizen, body="first")
    Comment.objects.create(service_request=assigned_request, author=officer, body="second")

    response = client_for(citizen).get(comments_url(assigned_request.pk))

    assert response.status_code == 200
    assert [c["body"] for c in response.data["results"]] == ["first", "second"]


def test_blank_comment_is_rejected(client_for, citizen, assigned_request):
    response = client_for(citizen).post(comments_url(assigned_request.pk), {"body": "   "})

    assert response.status_code == 400


def test_users_who_cannot_see_request_cannot_comment(client_for, make_user, assigned_request):
    for outsider in (make_user(Role.CITIZEN), make_user(Role.OFFICER)):
        client = client_for(outsider)
        assert client.get(comments_url(assigned_request.pk)).status_code == 404
        assert client.post(comments_url(assigned_request.pk), {"body": "x"}).status_code == 404
