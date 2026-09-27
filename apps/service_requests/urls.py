from rest_framework.routers import DefaultRouter

from .views import ServiceRequestViewSet

router = DefaultRouter()
router.register("requests", ServiceRequestViewSet, basename="request")

urlpatterns = router.urls
