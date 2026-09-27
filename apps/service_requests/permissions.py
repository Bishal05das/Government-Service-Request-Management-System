from rest_framework.permissions import BasePermission

from apps.accounts.models import Role

from .models import Status

TERMINAL_STATUSES = {Status.CLOSED, Status.REJECTED, Status.CANCELLED}


class CanCreateRequest(BasePermission):
    """Only citizens submit new service requests."""

    message = "Only citizens can submit service requests."

    def has_permission(self, request, view):
        if view.action != "create":
            return True
        return request.user.role == Role.CITIZEN


class CanEditRequestDetails(BasePermission):
    """
    Title/description/category/priority can be edited by:
    - the owning citizen while the request is still SUBMITTED;
    - an admin while the request is not in a terminal state.
    """

    message = "You cannot edit this request in its current state."

    def has_object_permission(self, request, view, obj):
        if view.action not in ("update", "partial_update"):
            return True
        user = request.user
        if user.role == Role.ADMIN:
            return obj.status not in TERMINAL_STATUSES
        if user.role == Role.CITIZEN:
            return obj.citizen_id == user.pk and obj.status == Status.SUBMITTED
        return False
