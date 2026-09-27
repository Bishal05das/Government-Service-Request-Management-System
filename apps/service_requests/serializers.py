import mimetypes
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.categories.models import Category

from .models import Attachment, Comment, ServiceRequest, Status, StatusChange
from .workflow import allowed_transitions


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name"]


class StatusChangeSerializer(serializers.ModelSerializer):
    changed_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = StatusChange
        fields = ["id", "from_status", "to_status", "changed_by", "note", "created_at"]


class ServiceRequestSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)
    citizen = UserSummarySerializer(read_only=True)
    assigned_officer = UserSummarySerializer(read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            "id", "title", "description", "category", "category_name", "priority", "status",
            "citizen", "assigned_officer", "assigned_at", "resolved_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "citizen", "assigned_officer", "assigned_at", "resolved_at",
            "created_at", "updated_at",
        ]

    def validate_category(self, category):
        if not category.is_active:
            raise serializers.ValidationError("This category is not accepting requests.")
        return category


class ServiceRequestDetailSerializer(ServiceRequestSerializer):
    status_history = StatusChangeSerializer(many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()

    class Meta(ServiceRequestSerializer.Meta):
        fields = ServiceRequestSerializer.Meta.fields + ["status_history", "allowed_transitions"]

    def get_allowed_transitions(self, obj) -> list[str]:
        return allowed_transitions(obj, self.context["request"].user)


class StatusChangeInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class AssignOfficerSerializer(serializers.Serializer):
    officer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.OFFICER, is_active=True),
        error_messages={"does_not_exist": "No active officer with id {pk_value}."},
    )


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    author_role = serializers.CharField(source="author.role", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "author_role", "body", "created_at"]
        read_only_fields = ["id", "author", "author_role", "created_at"]

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()


class AttachmentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    uploaded_by = UserSummarySerializer(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "file", "original_name", "content_type", "size", "uploaded_by",
                  "download_url", "created_at"]
        read_only_fields = ["id", "original_name", "content_type", "size", "uploaded_by",
                            "download_url", "created_at"]

    def get_download_url(self, obj) -> str:
        url = reverse("request-download-attachment", args=[obj.service_request_id, obj.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def validate_file(self, file):
        extension = Path(file.name).suffix.lower().lstrip(".")
        allowed = settings.ATTACHMENT_ALLOWED_EXTENSIONS
        if extension not in allowed:
            raise serializers.ValidationError(f"Unsupported file type. Allowed: {', '.join(allowed)}.")
        max_bytes = settings.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024
        if file.size > max_bytes:
            raise serializers.ValidationError(f"File exceeds {settings.ATTACHMENT_MAX_SIZE_MB} MB.")
        return file

    def create(self, validated_data):
        file = validated_data["file"]
        validated_data["original_name"] = Path(file.name).name[:255]
        # Derive the type from the (validated) extension rather than trusting the client header.
        validated_data["content_type"] = mimetypes.guess_type(validated_data["original_name"])[0] or ""
        validated_data["size"] = file.size
        return super().create(validated_data)
