"""Production login configuration cannot silently fall back to local cache."""
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from transactional.login_throttle import is_limited


@override_settings(DEBUG=False, POS_LOGIN_REDIS_URL="")
def test_production_login_fails_closed_without_shared_redis():
    with pytest.raises(ImproperlyConfigured, match="POS_LOGIN_REDIS_URL"):
        is_limited(("pos:login:ip:test", "pos:login:account:test"))
