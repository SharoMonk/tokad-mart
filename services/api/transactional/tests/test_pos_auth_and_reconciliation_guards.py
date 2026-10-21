"""Session idle timeout, throttling and cashier shift reconciliation gates."""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from transactional.models import (
    CashierShift, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Sale,
)


@pytest.fixture
def cashier(db):
    user = get_user_model().objects.create_user(
        username="auth-protection-cashier", password="good-password", is_staff=True,
    )
    location = POSLocation.objects.create(code="SAFE", name="Safe")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="T1")
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    return user, location, terminal, operator


def payload(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


@pytest.mark.django_db
@override_settings(POS_LOGIN_MAX_FAILURES=3, POS_LOGIN_WINDOW_SECONDS=120)
def test_failed_login_throttled_and_successful_login_remains_possible(cashier):
    cache.clear()
    client = Client(REMOTE_ADDR="127.0.0.51")
    url = "/api/transactional/pos/login/"
    for _ in range(3):
        assert payload(client, url, {
            "username": "auth-protection-cashier", "password": "bad"
        }).status_code == 403
    locked = payload(client, url, {
        "username": "auth-protection-cashier", "password": "good-password"
    })
    assert locked.status_code == 429
    assert locked["Retry-After"] == "60"
    cache.clear()
    success = payload(client, url, {
        "username": "auth-protection-cashier", "password": "good-password"
    })
    assert success.status_code == 200


@pytest.mark.django_db
@override_settings(POS_SESSION_IDLE_SECONDS=30)
def test_idle_session_expires_on_next_pos_request(cashier):
    user, _, _, _ = cashier
    client = Client()
    client.force_login(user)
    session = client.session
    session["pos_last_activity"] = int(timezone.now().timestamp()) - 31
    session.save()
    response = client.get("/api/transactional/pos/scope/")
    assert response.status_code == 401
    assert response.json()["error"] == "session_expired"
    assert not client.get("/api/transactional/pos/session/").json()["authenticated"]


@pytest.mark.django_db
def test_shift_close_rejects_incomplete_sale(cashier):
    user, location, terminal, operator = cashier
    shift = CashierShift.objects.create(
        location=location, terminal=terminal, operator=operator, opening_cash_minor=0,
    )
    import uuid
    Sale.objects.create(
        reference=uuid.uuid4(), location_code=location.code, currency="NGN",
        total_minor=10000, status=Sale.Status.PENDING_PAYMENT, shift=shift,
    )
    client = Client()
    client.force_login(user)
    response = payload(client, f"/api/transactional/pos/shifts/{shift.pk}/close/", {
        "closing_cash_minor": 0,
    })
    assert response.status_code == 400
    shift.refresh_from_db()
    assert shift.status == CashierShift.Status.OPEN
