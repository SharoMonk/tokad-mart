"""Atomic Redis reservation contract without requiring a running Redis service."""
from unittest.mock import patch

from django.test import override_settings

from transactional import login_throttle


@override_settings(
    DEBUG=False, POS_LOGIN_REDIS_URL="redis://localhost:6379/1",
    POS_LOGIN_MAX_FAILURES=5, POS_LOGIN_MAX_IP_ATTEMPTS=50,
    POS_LOGIN_WINDOW_SECONDS=900,
)
def test_production_reservation_is_one_atomic_operation():
    class FakeRedis:
        def __init__(self):
            self.calls = []
            self.deleted = []
        def eval(self, script, nkeys, *args):
            self.calls.append((script, nkeys, args))
            return 0
        def delete(self, key):
            self.deleted.append(key)

    redis = FakeRedis()
    keys = ("pos:login:ip:hashed", "pos:login:account:hashed")
    with patch.object(login_throttle, "_redis", return_value=redis):
        assert login_throttle.is_limited(keys) is False
        assert len(redis.calls) == 1
        script, nkeys, args = redis.calls[0]
        assert nkeys == 2
        assert args == (*keys, 50, 5, 900)
        assert "redis.call('INCR'" in script
        login_throttle.record_failure(keys)
        assert len(redis.calls) == 1  # attempt already counted
        login_throttle.clear_account_failures(keys)
        assert redis.deleted == [keys[1]]
