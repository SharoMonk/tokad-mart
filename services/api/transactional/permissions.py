from rest_framework.permissions import BasePermission


class IsPOSOperator(BasePermission):
    """Allow authenticated staff users to operate the POS API."""

    message = "POS operator permission is required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
        )
