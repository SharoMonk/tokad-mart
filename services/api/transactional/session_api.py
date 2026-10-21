"""Cookie-backed POS login with Django session and CSRF protection."""
import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured
from .login_throttle import login_keys, is_limited, record_failure, clear_account_failures
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
    role = POSOperator.objects.get(user=user).role if authenticated else None
    return JsonResponse({
        "authenticated": authenticated,
        "username": user.get_username() if authenticated else None,
        "role": role,
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
    keys = login_keys(request, username)
    if is_limited(keys):
        response = JsonResponse({"error": "login_temporarily_limited"}, status=429)
        response["Retry-After"] = "60"
        return response
    user = authenticate(request, username=username, password=password)
    if not user or not user.is_active or not user.is_staff or not POSOperator.objects.filter(
        user=user, is_active=True
    ).exists():
        record_failure(keys)
        return JsonResponse({"error": "invalid_credentials_or_operator"}, status=403)
    login(request, user)
    clear_account_failures(keys)
    request.session["pos_last_activity"] = int(timezone.now().timestamp())
    return JsonResponse({"authenticated": True, "username": user.get_username(), "role": POSOperator.objects.get(user=user).role})


@require_POST
@csrf_protect
def pos_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False})
