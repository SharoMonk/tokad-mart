"""Rate-limit POS login failures with bounded cache counters.

Production MUST provide a shared cache (e.g. Redis) across workers.
LocMemCache is suitable only for local development and unit tests.
"""
import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache


def _key(label, value):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"pos:login:{label}:{digest}"


def _client_address(request):
    # Do not trust X-Forwarded-For: proxy headers can be spoofed unless
    # an explicitly configured trusted reverse proxy validates/sets them.
    raw = request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return "unknown"


def login_keys(request, username):
    name = username.strip().casefold()
    return (_key("ip", _client_address(request)), _key("account", name))


def is_limited(keys):
    threshold = settings.POS_LOGIN_MAX_FAILURES
    return any(int(cache.get(key, 0)) >= threshold for key in keys)


def record_failure(keys):
    period = settings.POS_LOGIN_WINDOW_SECONDS
    for key in keys:
        # Cache.add is atomic on supported cache backends; incr preserves
        # existing expiry. Lockout counters do not include cleartext IDs.
        if not cache.add(key, 1, timeout=period):
            try:
                cache.incr(key)
            except ValueError:
                cache.add(key, 1, timeout=period)


def clear_account_failures(keys):
    # Preserve the IP counter to prevent an attacker from alternating
    # successful and failing account attempts to evade network throttles.
    cache.delete(keys[1])
