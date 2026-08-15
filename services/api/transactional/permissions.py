from rest_framework.permissions import BasePermission


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

        try:
            return bool(user.pos_operator.is_active)
        except user.__class__.pos_operator.RelatedObjectDoesNotExist:
            return False
