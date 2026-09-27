from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "actor", "target_type", "target_id", "ip_address"]
    list_filter = ["action", "target_type"]
    search_fields = ["actor__email", "target_id"]

    # Audit entries are append-only, also in the Django admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
