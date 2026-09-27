from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrReadOnly

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

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Category is used by existing requests; deactivate it instead."},
                status=status.HTTP_409_CONFLICT,
            )
