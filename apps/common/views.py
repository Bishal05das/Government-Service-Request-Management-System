from django.core.cache import cache
from django.db import connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(responses=OpenApiTypes.OBJECT, tags=["health"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness/readiness probe: confirms the API, database and cache (Redis) are reachable."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    cache.set("health-check", "ok", timeout=5)
    return Response({"status": "ok"})
