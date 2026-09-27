from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin

from .permissions import CanCreateRequest, CanEditRequestDetails
from .selectors import visible_requests_for
from .serializers import (
    AssignOfficerSerializer,
    ServiceRequestDetailSerializer,
    ServiceRequestSerializer,
    StatusChangeInputSerializer,
)
from .workflow import assign_officer, change_status, record_status_change


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
        if self.action in ("retrieve", "change_status", "assign"):
            queryset = queryset.prefetch_related("status_history__changed_by")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ServiceRequestDetailSerializer
        if self.action == "change_status":
            return StatusChangeInputSerializer
        if self.action == "assign":
            return AssignOfficerSerializer
        return ServiceRequestSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        service_request = serializer.save(citizen=self.request.user)
        record_status_change(service_request, "", self.request.user)

    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        """Move the request through its workflow (see `allowed_transitions` on the detail view)."""
        service_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        change_status(
            service_request,
            serializer.validated_data["status"],
            request.user,
            serializer.validated_data["note"],
        )

        return self._detail_response(service_request)

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def assign(self, request, pk=None):
        """Admin only: assign or reassign an active officer to the request."""
        service_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assign_officer(service_request, serializer.validated_data["officer"], request.user)
        return self._detail_response(service_request)

    def _detail_response(self, service_request):
        service_request = self.get_queryset().get(pk=service_request.pk)
        return Response(ServiceRequestDetailSerializer(service_request, context={"request": self.request}).data)
