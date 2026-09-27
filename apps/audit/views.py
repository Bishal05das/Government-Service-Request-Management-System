import django_filters
from rest_framework import viewsets

from apps.accounts.permissions import IsAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["action", "actor", "target_type", "target_id"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin only, read-only: who did what, to which object, and when."""

    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    filterset_class = AuditLogFilter
    search_fields = ["actor__email", "target_id"]
    ordering_fields = ["created_at"]
