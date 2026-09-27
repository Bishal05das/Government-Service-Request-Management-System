from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ServiceRequestViewSet, StatisticsView

router = DefaultRouter()
router.register("requests", ServiceRequestViewSet, basename="request")

urlpatterns = [
    path("admin/statistics/", StatisticsView.as_view(), name="admin-statistics"),
] + router.urls
