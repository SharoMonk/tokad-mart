"""Supervisor-only reviews preserve the immutable cashier cash count."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from transactional.models import (
    AuditEvent, CashierShift, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal, ShiftReconciliationReview,
)


@pytest.mark.django_db
def test_supervisor_review_requires_role_and_does_not_change_cash():
    location = POSLocation.objects.create(code="A", name="Main")
    terminal = POSTerminal.objects.create(location=location, code="A1", name="Register")
    cashier = get_user_model().objects.create_user("shift-worker", password="test", is_staff=True)
    supervisor = get_user_model().objects.create_user("shift-supervisor", password="test", is_staff=True)
    operator = POSOperator.objects.create(user=cashier)
    manager = POSOperator.objects.create(user=supervisor, role=POSOperator.Role.SUPERVISOR)
    for profile in (operator, manager):
        POSOperatorLocation.objects.create(operator=profile, location=location)
        POSOperatorTerminal.objects.create(operator=profile, terminal=terminal)
    shift = CashierShift.objects.create(
        operator=operator, location=location, terminal=terminal,
        status=CashierShift.Status.CLOSED,
        opening_cash_minor=50000, closing_cash_minor=70000,
        expected_cash_minor=80000,
    )
    url = f"/api/transactional/pos/shifts/{shift.pk}/review/"
    body = json.dumps({"decision": "REJECTED", "notes": "Cash shortage requires investigation"})

    client = Client()
    client.force_login(cashier)
    assert client.post(url, body, content_type="application/json").status_code == 403
    client.force_login(supervisor)
    assert client.get(url).json()["variance_minor"] == -10000
    first = client.post(url, body, content_type="application/json")
    assert first.status_code == 201
    assert first.json()["decision"] == "REJECTED"
    assert client.post(url, body, content_type="application/json").status_code == 409
    shift.refresh_from_db()
    assert shift.expected_cash_minor == 80000
    assert shift.closing_cash_minor == 70000
    assert ShiftReconciliationReview.objects.count() == 1
    assert AuditEvent.objects.filter(action="shift.reconciliation_reviewed").count() == 1


@pytest.mark.django_db
def test_supervisor_cannot_review_open_shift():
    location = POSLocation.objects.create(code="B", name="Store")
    terminal = POSTerminal.objects.create(location=location, code="B1", name="Register")
    user = get_user_model().objects.create_user("supervisor-b", password="test", is_staff=True)
    operator = POSOperator.objects.create(user=user, role=POSOperator.Role.SUPERVISOR)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    cashier = get_user_model().objects.create_user(
        "cashier-b", password="test", is_staff=True
    )
    cashier_operator = POSOperator.objects.create(user=cashier)
    shift = CashierShift.objects.create(
        operator=cashier_operator, location=location, terminal=terminal
    )
    client = Client()
    client.force_login(user)
    response = client.post(
        f"/api/transactional/pos/shifts/{shift.pk}/review/",
        json.dumps({"decision": "APPROVED", "notes": "Verified"}),
        content_type="application/json",
    )
    assert response.status_code == 409
    assert ShiftReconciliationReview.objects.count() == 0
