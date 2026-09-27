from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditAction(models.TextChoices):
    USER_REGISTERED = "USER_REGISTERED", "User registered"
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED", "Login succeeded"
    LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
    EMAIL_VERIFIED = "EMAIL_VERIFIED", "Email verified"
    USER_CREATED = "USER_CREATED", "User created by admin"
    USER_UPDATED = "USER_UPDATED", "User updated by admin"
    CATEGORY_CREATED = "CATEGORY_CREATED", "Category created"
    CATEGORY_UPDATED = "CATEGORY_UPDATED", "Category updated"
    CATEGORY_DELETED = "CATEGORY_DELETED", "Category deleted"
    REQUEST_CREATED = "REQUEST_CREATED", "Request created"
    REQUEST_UPDATED = "REQUEST_UPDATED", "Request updated"
    REQUEST_STATUS_CHANGED = "REQUEST_STATUS_CHANGED", "Request status changed"
    OFFICER_ASSIGNED = "OFFICER_ASSIGNED", "Officer assigned"
    COMMENT_ADDED = "COMMENT_ADDED", "Comment added"
    ATTACHMENT_UPLOADED = "ATTACHMENT_UPLOADED", "Attachment uploaded"
    ATTACHMENT_DOWNLOADED = "ATTACHMENT_DOWNLOADED", "Attachment downloaded"


class AuditLog(models.Model):
    """Append-only record of security-relevant and business actions."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="Null for anonymous actions such as a failed login.",
    )
    action = models.CharField(max_length=32, choices=AuditAction.choices)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    changes = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} by {self.actor_id or 'anonymous'}"
