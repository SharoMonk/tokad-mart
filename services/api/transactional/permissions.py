from rest_framework.permissions import BasePermission

from .models import POSOperator


class IsPOSOperator(BasePermission):
    """Allow authenticated staff users with an active POS operator profile."""

    message = "POS operator permission is required."

    def has_permission(self, request, view) -> bool:
        user = request.user

        if not (
            user
            and user.is_authenticated
            and user.is_staff
        ):
            return False

        return POSOperator.objects.filter(
            user=user,
            is_active=True,
        ).exists()
