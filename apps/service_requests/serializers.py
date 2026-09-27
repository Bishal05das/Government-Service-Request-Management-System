from rest_framework import serializers

from apps.accounts.models import User
from apps.categories.models import Category

from .models import ServiceRequest, Status, StatusChange
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
