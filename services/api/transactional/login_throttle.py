"""Atomic Redis-backed rate limiting for production, local cache for development.

Production checks and increments are executed by Redis Lua scripts atomically.
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


# The check is atomic across the IP and account keys.
_CHECK = """
local max = tonumber(ARGV[1])
for i = 1, #KEYS do
  if tonumber(redis.call('GET', KEYS[i]) or '0') >= max then
    return 1
  end
end
return 0
"""

# Atomic increments preserve the fixed window's initial TTL.
_FAIL = """
local ttl = tonumber(ARGV[1])
for i = 1, #KEYS do
  local value = redis.call('INCR', KEYS[i])
  if value == 1 then redis.call('EXPIRE', KEYS[i], ttl) end
end
return 1
"""


def is_limited(keys):
    redis = _redis()
    if redis is not None:
        return bool(redis.eval(_CHECK, len(keys), *keys, settings.POS_LOGIN_MAX_FAILURES))
    return any(int(cache.get(key, 0)) >= settings.POS_LOGIN_MAX_FAILURES for key in keys)


def record_failure(keys):
    redis = _redis()
    if redis is not None:
        redis.eval(_FAIL, len(keys), *keys, settings.POS_LOGIN_WINDOW_SECONDS)
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
