"""Unprivileged readiness probe with an actual database connection check."""
from django.db import connections, OperationalError
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def readiness(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (OperationalError, Exception):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
