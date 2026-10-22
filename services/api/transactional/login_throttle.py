"""Atomic Redis-backed rate limiting for production, local cache for development.

Production attempts are reserved using one atomic Redis Lua script.
Every API worker must point at the same authenticated Redis instance.
"""
import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured


def _key(label, value):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"pos:login:{label}:{digest}"


def _client_address(request):
    # Never trust unvalidated client-supplied X-Forwarded-For.
    raw = request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return "unknown"


def login_keys(request, username):
    name = username.strip().casefold()
    return (_key("ip", _client_address(request)), _key("account", name))


def _redis():
    if settings.DEBUG and not getattr(settings, "POS_LOGIN_REDIS_URL", ""):
        return None
    url = getattr(settings, "POS_LOGIN_REDIS_URL", "")
    if not url:
        raise ImproperlyConfigured("POS_LOGIN_REDIS_URL is required outside DEBUG mode")
    from redis import Redis
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


# Reserve both counters atomically before checking credentials. This prevents
# concurrent login bursts from crossing the configured account threshold.
# Keys order: client IP, account. TTL is a fixed window from first attempt.
_RESERVE = """
local ipmax = tonumber(ARGV[1])
local accountmax = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
if tonumber(redis.call('GET', KEYS[1]) or '0') >= ipmax then return 1 end
if tonumber(redis.call('GET', KEYS[2]) or '0') >= accountmax then return 1 end
for i = 1, 2 do
  local n = redis.call('INCR', KEYS[i])
  if n == 1 then redis.call('EXPIRE', KEYS[i], ttl) end
end
return 0
"""


def is_limited(keys):
    redis = _redis()
    if redis is not None:
        return bool(redis.eval(
            _RESERVE, 2, *keys,
            settings.POS_LOGIN_MAX_IP_ATTEMPTS,
            settings.POS_LOGIN_MAX_FAILURES,
            settings.POS_LOGIN_WINDOW_SECONDS,
        ))
    return any(int(cache.get(key, 0)) >= settings.POS_LOGIN_MAX_FAILURES for key in keys)


def record_failure(keys):
    # Production attempts were already charged atomically before authenticate().
    if _redis() is not None:
        return
    for key in keys:
        if not cache.add(key, 1, timeout=settings.POS_LOGIN_WINDOW_SECONDS):
            try:
                cache.incr(key)
            except ValueError:
                cache.add(key, 1, timeout=settings.POS_LOGIN_WINDOW_SECONDS)


def clear_account_failures(keys):
    redis = _redis()
    if redis is not None:
        redis.delete(keys[1])
    else:
        cache.delete(keys[1])
