import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import Role
from apps.service_requests.models import Status

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def assigned_request(citizen, officer, make_request):
    return make_request(citizen, status=Status.ASSIGNED, assigned_officer=officer)


def attachments_url(pk):
    return reverse("request-attachments", args=[pk])


def upload(client, request_pk, name="photo.png", content=b"fake-image-bytes"):
    file = SimpleUploadedFile(name, content, content_type="image/png")
    return client.post(attachments_url(request_pk), {"file": file}, format="multipart")


def test_owner_uploads_attachment(client_for, citizen, assigned_request):
    response = upload(client_for(citizen), assigned_request.pk)

    assert response.status_code == 201
    assert response.data["original_name"] == "photo.png"
    assert response.data["content_type"] == "image/png"
    assert response.data["size"] == len(b"fake-image-bytes")
    assert response.data["uploaded_by"]["id"] == citizen.pk
    stored = assigned_request.attachments.get()
    assert "photo" not in stored.file.name  # stored under a random name


def test_assigned_officer_can_upload_and_list(client_for, officer, assigned_request):
    client = client_for(officer)
    upload(client, assigned_request.pk, name="report.pdf")

    response = client.get(attachments_url(assigned_request.pk))

    assert response.status_code == 200
    assert [a["original_name"] for a in response.data["results"]] == ["report.pdf"]


def test_download_returns_file_content(client_for, citizen, officer, assigned_request):
    attachment_id = upload(client_for(citizen), assigned_request.pk).data["id"]

    response = client_for(officer).get(
        reverse("request-download-attachment", args=[assigned_request.pk, attachment_id])
    )

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"fake-image-bytes"
    assert 'filename="photo.png"' in response["Content-Disposition"]


def test_disallowed_extension_is_rejected(client_for, citizen, assigned_request):
    response = upload(client_for(citizen), assigned_request.pk, name="script.exe")

    assert response.status_code == 400


def test_oversized_file_is_rejected(settings, client_for, citizen, assigned_request):
    settings.ATTACHMENT_MAX_SIZE_MB = 0

    response = upload(client_for(citizen), assigned_request.pk)

    assert response.status_code == 400


def test_outsiders_cannot_upload_list_or_download(client_for, citizen, make_user, assigned_request):
    attachment_id = upload(client_for(citizen), assigned_request.pk).data["id"]
    download_url = reverse("request-download-attachment", args=[assigned_request.pk, attachment_id])

    for outsider in (make_user(Role.CITIZEN), make_user(Role.OFFICER)):
        client = client_for(outsider)
        assert upload(client, assigned_request.pk).status_code == 404
        assert client.get(attachments_url(assigned_request.pk)).status_code == 404
        assert client.get(download_url).status_code == 404


def test_attachment_id_must_belong_to_request(client_for, citizen, admin_user, make_request, assigned_request):
    attachment_id = upload(client_for(citizen), assigned_request.pk).data["id"]
    other_request = make_request(citizen)

    response = client_for(admin_user).get(
        reverse("request-download-attachment", args=[other_request.pk, attachment_id])
    )

    assert response.status_code == 404
