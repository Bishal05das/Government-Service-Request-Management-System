from django.contrib import admin

from .models import ServiceRequest, StatusChange


class StatusChangeInline(admin.TabularInline):
    model = StatusChange
    extra = 0
    readonly_fields = ["from_status", "to_status", "changed_by", "note", "created_at"]
    can_delete = False


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "category", "priority", "status", "citizen", "assigned_officer", "created_at"]
    list_filter = ["status", "priority", "category"]
    search_fields = ["title", "description", "citizen__email"]
    raw_id_fields = ["citizen", "assigned_officer"]
    inlines = [StatusChangeInline]
