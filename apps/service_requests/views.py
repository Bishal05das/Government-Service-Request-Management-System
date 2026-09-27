from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import StatusChange
from .permissions import CanCreateRequest, CanEditRequestDetails
from .selectors import visible_requests_for
from .serializers import ServiceRequestDetailSerializer, ServiceRequestSerializer


class ServiceRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            mixins.CreateModelMixin, mixins.UpdateModelMixin,
                            viewsets.GenericViewSet):
    """
    Citizens submit and track their own requests, officers work on requests
    assigned to them, admins see everything.
    """

    permission_classes = [IsAuthenticated, CanCreateRequest, CanEditRequestDetails]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["status", "priority", "category", "assigned_officer", "citizen"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "priority_rank", "status"]

    def get_queryset(self):
        queryset = visible_requests_for(self.request.user)
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("status_history__changed_by")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ServiceRequestDetailSerializer
        return ServiceRequestSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        service_request = serializer.save(citizen=self.request.user)
        StatusChange.objects.create(
            service_request=service_request,
            to_status=service_request.status,
            changed_by=self.request.user,
        )
