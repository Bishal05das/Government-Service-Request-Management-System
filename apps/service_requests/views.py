from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.audit.models import AuditAction
from apps.audit.services import diff, record

from .notifications import notify_new_comment
from .permissions import CanCreateRequest, CanEditRequestDetails
from .selectors import visible_requests_for
from .statistics import build_statistics
from .serializers import (
    AssignOfficerSerializer,
    AttachmentSerializer,
    CommentSerializer,
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

    def get_throttles(self):
        # Uploads are expensive (disk + bandwidth), so they get their own tighter budget.
        if self.action == "attachments" and self.request.method == "POST":
            self.throttle_scope = "uploads"
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ServiceRequestDetailSerializer
        if self.action == "change_status":
            return StatusChangeInputSerializer
        if self.action == "assign":
            return AssignOfficerSerializer
        if self.action == "comments":
            return CommentSerializer
        if self.action == "attachments":
            return AttachmentSerializer
        return ServiceRequestSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        service_request = serializer.save(citizen=self.request.user)
        record_status_change(service_request, "", self.request.user)
        record(AuditAction.REQUEST_CREATED, request=self.request, target=service_request,
               changes={"title": service_request.title, "category": service_request.category_id,
                        "priority": service_request.priority})

    def perform_update(self, serializer):
        changes = diff(serializer.instance, serializer.validated_data)
        service_request = serializer.save()
        if changes:
            record(AuditAction.REQUEST_UPDATED, request=self.request, target=service_request, changes=changes)

    @extend_schema(request=StatusChangeInputSerializer, responses=ServiceRequestDetailSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        """Move the request through its workflow (see `allowed_transitions` on the detail view)."""
        service_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous = service_request.status
        updated = change_status(
            service_request,
            serializer.validated_data["status"],
            request.user,
            serializer.validated_data["note"],
        )
        record(AuditAction.REQUEST_STATUS_CHANGED, request=request, target=updated,
               changes={"status": {"from": previous, "to": updated.status},
                        "note": serializer.validated_data["note"]})
        return self._detail_response(service_request)

    @extend_schema(request=AssignOfficerSerializer, responses=ServiceRequestDetailSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def assign(self, request, pk=None):
        """Admin only: assign or reassign an active officer to the request."""
        service_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_officer = service_request.assigned_officer_id
        updated = assign_officer(service_request, serializer.validated_data["officer"], request.user)
        record(AuditAction.OFFICER_ASSIGNED, request=request, target=updated,
               changes={"assigned_officer": {"from": previous_officer, "to": updated.assigned_officer_id}})
        return self._detail_response(service_request)

    @extend_schema(methods=["GET"], responses=CommentSerializer(many=True))
    @extend_schema(methods=["POST"], request=CommentSerializer, responses={201: CommentSerializer})
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """List or add comments. Anyone who can view the request can take part."""
        service_request = self.get_object()
        if request.method == "GET":
            comments = service_request.comments.select_related("author")
            page = self.paginate_queryset(comments)
            return self.get_paginated_response(self.get_serializer(page, many=True).data)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(service_request=service_request, author=request.user)
        record(AuditAction.COMMENT_ADDED, request=request, target=service_request,
               changes={"comment_id": comment.pk})
        notify_new_comment(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(methods=["GET"], responses=AttachmentSerializer(many=True))
    @extend_schema(methods=["POST"], request={"multipart/form-data": AttachmentSerializer},
                   responses={201: AttachmentSerializer})
    @action(detail=True, methods=["get", "post"], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def attachments(self, request, pk=None):
        """List attachments, or upload one as multipart/form-data (field name: `file`)."""
        service_request = self.get_object()
        if request.method == "GET":
            attachments = service_request.attachments.select_related("uploaded_by")
            page = self.paginate_queryset(attachments)
            return self.get_paginated_response(self.get_serializer(page, many=True).data)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save(service_request=service_request, uploaded_by=request.user)
        record(AuditAction.ATTACHMENT_UPLOADED, request=request, target=service_request,
               changes={"attachment_id": attachment.pk, "name": attachment.original_name,
                        "size": attachment.size})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_id>\d+)/download")
    def download_attachment(self, request, pk=None, attachment_id=None):
        """Stream an attachment. Files are never served publicly, only through this check."""
        service_request = self.get_object()
        attachment = get_object_or_404(service_request.attachments, pk=attachment_id)
        record(AuditAction.ATTACHMENT_DOWNLOADED, request=request, target=service_request,
               changes={"attachment_id": attachment.pk})
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_name,
            content_type=attachment.content_type or "application/octet-stream",
        )

    def _detail_response(self, service_request):
        service_request = self.get_queryset().get(pk=service_request.pk)
        return Response(ServiceRequestDetailSerializer(service_request, context={"request": self.request}).data)


class StatisticsView(APIView):
    """Admin dashboard figures: request counts, category breakdown and officer workload."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT, tags=["admin"])
    def get(self, request):
        return Response(build_statistics())
