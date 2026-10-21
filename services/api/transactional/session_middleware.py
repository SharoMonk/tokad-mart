"""Server-enforced inactivity expiry for authenticated POS sessions."""
from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone


class POSSessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not path.startswith("/api/transactional/pos/"):
            return self.get_response(request)
        if path.endswith("/login/") or path.endswith("/logout/"):
            return self.get_response(request)
        if not request.user.is_authenticated:
            return self.get_response(request)

        now = int(timezone.now().timestamp())
        last = request.session.get("pos_last_activity")
        limit = settings.POS_SESSION_IDLE_SECONDS
        if last is not None and now - int(last) >= limit:
            logout(request)
            if path.endswith("/session/"):
                return self.get_response(request)
            return JsonResponse({"error": "session_expired", "message": "Sign in again."}, status=401)
        request.session["pos_last_activity"] = now
        return self.get_response(request)
