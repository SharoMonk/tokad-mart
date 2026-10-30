"""Financial dashboard, scoped expense recording and independent review."""
import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from transactional.models import (
    AuditEvent, CashierShift, ExpenseReview, POSLocation, POSOperator,
    POSOperatorLocation, POSOperatorTerminal, POSTerminal, Sale, StoreExpense,
)


@pytest.fixture
def finance_setup(db):
    location = POSLocation.objects.create(code="FINANCE", name="Main finance")
    terminal = POSTerminal.objects.create(location=location, code="F1", name="Front")
    clients = []
    operators = []
    for username, role in (
        ("fin-owner", POSOperator.Role.SUPERVISOR),
        ("fin-auditor", POSOperator.Role.SUPERVISOR),
        ("fin-cashier", POSOperator.Role.OPERATOR),
    ):
        user = get_user_model().objects.create_user(
            username, password="test", is_staff=True
        )
        operator = POSOperator.objects.create(user=user, role=role)
        POSOperatorLocation.objects.create(operator=operator, location=location)
        POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
        c = Client()
        c.force_login(user)
        clients.append(c)
        operators.append(operator)
    return clients, operators, location, terminal


def scoped(**kwargs):
    return {"location_code": "FINANCE", "terminal_code": "F1", **kwargs}


def post(client, path, data):
    return client.post(path, json.dumps(data), content_type="application/json")


@pytest.mark.django_db
def test_expenses_independent_review_and_unique_reference(finance_setup):
    (owner, auditor, cashier), operators, location, terminal = finance_setup
    url = "/api/transactional/pos/manage/expenses/"
    body = scoped(
        reference="EXP-100", category="Electricity",
        description="Meter recharge", amount_minor=155000,
        incurred_on=date.today().isoformat(),
    )
    assert post(cashier, url, body).status_code == 403
    assert post(owner, url, {**body, "location_code": "OTHER"}).status_code == 403
    created = post(owner, url, body)
    assert created.status_code == 201, created.content
    assert post(owner, url, body).status_code == 409
    expense = StoreExpense.objects.get(reference="EXP-100")
    review_url = f"{url}{expense.pk}/review/"
    review = scoped(decision="APPROVED", notes="Checked receipt")
    assert post(owner, review_url, review).status_code == 403
    assert post(cashier, review_url, review).status_code == 403
    assert post(auditor, review_url, review).status_code == 200
    assert post(auditor, review_url, review).status_code == 409
    assert ExpenseReview.objects.filter(expense=expense).count() == 1
    assert AuditEvent.objects.filter(action="expense.reviewed").count() == 1


@pytest.mark.django_db
def test_dashboard_scopes_sales_shifts_and_reviewed_expenses(finance_setup):
    (owner, auditor, cashier), operators, location, terminal = finance_setup
    today = timezone.localdate()
    sale = Sale.objects.create(
        reference="60e40c1c-8446-4e41-a58d-21722e2a0350",
        location_code=location.code, currency="NGN",
        subtotal_minor=360000, total_minor=360000,
        status=Sale.Status.COMPLETED, completed_at=timezone.now(),
    )
    CashierShift.objects.create(
        operator=operators[2], location=location, terminal=terminal,
        status=CashierShift.Status.CLOSED, opening_cash_minor=0,
        closing_cash_minor=340000, expected_cash_minor=360000,
        closed_at=timezone.now(),
    )
    expense = StoreExpense.objects.create(
        location=location, reference="EXP-DASH",
        category="Rent", description="Daily cost",
        amount_minor=50000, incurred_on=today,
        recorded_by=operators[0],
    )
    ExpenseReview.objects.create(
        expense=expense, reviewed_by=operators[1],
        decision="APPROVED", notes="Verified",
    )
    url = "/api/transactional/pos/manage/financial-dashboard/"
    params = scoped(start=today.isoformat(), end=today.isoformat())
    assert cashier.get(url, params).status_code == 403
    assert owner.get(url, scoped(**{**params, "location_code": "OTHER"})).status_code == 403
    assert owner.get(url, scoped(start="bad", end=today.isoformat())).status_code == 400
    report = owner.get(url, params)
    assert report.status_code == 200, report.content
    data = report.json()
    assert data["sales"]["gross_minor"] == 360000
    assert data["sales"]["completed_sale_count"] == 1
    assert data["expenses"]["approved_minor"] == 50000
    assert data["cashier_shifts"][0]["variance_minor"] == -20000
    assert data["cashier_shifts"][0]["review_status"] == "PENDING"
