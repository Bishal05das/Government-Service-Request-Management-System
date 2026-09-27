from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrReadOnly
from apps.audit.models import AuditAction
from apps.audit.services import diff, record

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """
    Service categories. Everyone signed in can list them (non-admins only see
    active ones); only admins can create, update or delete.
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        queryset = Category.objects.all()
        if not getattr(self.request.user, "is_admin", False):
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_create(self, serializer):
        category = serializer.save()
        record(AuditAction.CATEGORY_CREATED, request=self.request, target=category,
               changes={"name": category.name})

    def perform_update(self, serializer):
        changes = diff(serializer.instance, serializer.validated_data)
        category = serializer.save()
        if changes:
            record(AuditAction.CATEGORY_UPDATED, request=self.request, target=category, changes=changes)

    @transaction.atomic
    def perform_destroy(self, instance):
        # Logged first so the entry keeps the id; a blocked delete rolls both back.
        record(AuditAction.CATEGORY_DELETED, request=self.request, target=instance,
               changes={"name": instance.name})
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Category is used by existing requests; deactivate it instead."},
                status=status.HTTP_409_CONFLICT,
            )
