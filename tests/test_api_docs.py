import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_openapi_schema_is_generated(api_client):
    response = api_client.get(reverse("schema"), {"format": "json"})

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/requests/{id}/status/" in paths
    assert "/api/v1/requests/{id}/assign/" in paths
    assert "/api/v1/admin/statistics/" in paths


@pytest.mark.parametrize("url_name", ["swagger-ui", "redoc"])
def test_docs_ui_is_served(api_client, url_name):
    assert api_client.get(reverse(url_name)).status_code == 200
