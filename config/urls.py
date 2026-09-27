from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("apps.common.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.categories.urls")),
    path("", include("apps.service_requests.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
