from rest_framework.permissions import BasePermission


class IsManagerOrOwner(BasePermission):
    """Allows privileged inventory/cash operations."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.groups.filter(name__in=["Manager", "Owner"]).exists()))


class CanOperatePOS(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.groups.filter(name__in=["Cashier", "Manager", "Owner"]).exists()))
