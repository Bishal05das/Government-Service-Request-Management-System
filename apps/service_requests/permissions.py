from rest_framework.permissions import BasePermission

from apps.accounts.models import Role


class CanCreateRequest(BasePermission):
    """Only citizens submit new service requests."""

    message = "Only citizens can submit service requests."

    def has_permission(self, request, view):
        if view.action != "create":
            return True
        return request.user.role == Role.CITIZEN
