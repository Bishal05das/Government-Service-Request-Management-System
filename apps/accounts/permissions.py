from rest_framework.permissions import BasePermission

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
