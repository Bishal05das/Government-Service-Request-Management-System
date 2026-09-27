from rest_framework import serializers

from apps.accounts.models import User
from apps.categories.models import Category

from .models import ServiceRequest, StatusChange


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

    class Meta(ServiceRequestSerializer.Meta):
        fields = ServiceRequestSerializer.Meta.fields + ["status_history"]
