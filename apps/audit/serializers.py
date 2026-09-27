from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "action", "actor", "actor_email", "target_type", "target_id",
                  "changes", "ip_address"]
        read_only_fields = fields
