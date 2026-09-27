from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role


class HasRole(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsCitizen(HasRole):
    allowed_roles = (Role.CITIZEN,)


class IsOfficer(HasRole):
    allowed_roles = (Role.OFFICER,)


class IsAdmin(HasRole):
    allowed_roles = (Role.ADMIN,)


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user may read; only admins may write."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or user.role == Role.ADMIN
