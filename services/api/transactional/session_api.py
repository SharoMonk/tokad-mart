"""Cookie-backed POS login with Django session and CSRF protection."""
import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import POSOperator


@require_GET
@ensure_csrf_cookie
def pos_session(request):
    user = request.user
    authenticated = bool(
        user.is_authenticated and user.is_active and user.is_staff
        and POSOperator.objects.filter(user=user, is_active=True).exists()
    )
    return JsonResponse({
        "authenticated": authenticated,
        "username": user.get_username() if authenticated else None,
    })


@require_POST
@csrf_protect
def pos_login(request):
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError()
        username = payload.get("username")
        password = payload.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError()
    except (UnicodeDecodeError, ValueError, TypeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    user = authenticate(request, username=username, password=password)
    if not user or not user.is_active or not user.is_staff or not POSOperator.objects.filter(
        user=user, is_active=True
    ).exists():
        return JsonResponse({"error": "invalid_credentials_or_operator"}, status=403)
    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@require_POST
@csrf_protect
def pos_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False})
