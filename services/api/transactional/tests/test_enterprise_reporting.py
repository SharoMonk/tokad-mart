"""Enterprise reporting is authorized by assigned locations and safe for CSV."""
import csv
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from transactional.models import (
    CashierShift, ExpenseReview, InventoryItem, POSLocation, POSOperator,
    POSOperatorLocation, POSTerminal, Product, Sale, StoreExpense,
)


@pytest.fixture
def stores(db):
    a = POSLocation.objects.create(code="STORE-A", name="Store A")
    b = POSLocation.objects.create(code="STORE-B", name="=HYPERLINK(1)")
    terminal = POSTerminal.objects.create(location=a, code="T1", name="Register")
    sup = get_user_model().objects.create_user("store-supervisor", is_staff=True)
    cashier = get_user_model().objects.create_user("store-operator", is_staff=True)
    operator = POSOperator.objects.create(user=sup, role="SUPERVISOR")
    POSOperatorLocation.objects.create(operator=operator, location=a)
    POSOperator.objects.create(user=cashier, role="OPERATOR")
    client = Client()
    client.force_login(sup)
    other = Client()
    other.force_login(cashier)
    today = timezone.localdate()
    for loc, amount in ((a, 10000), (b, 90000)):
        Sale.objects.create(
            reference=uuid4(), location_code=loc.code, currency="NGN",
            total_minor=amount, subtotal_minor=amount,
            status=Sale.Status.COMPLETED, completed_at=timezone.now(),
        )
    CashierShift.objects.create(
        operator=operator, location=a, terminal=terminal,
        status=CashierShift.Status.CLOSED,
        opening_cash_minor=0, expected_cash_minor=12000,
        closing_cash_minor=11000, closed_at=timezone.now(),
    )
    product = Product.objects.create(
        sku="=FORMULA()", name="@Excel injection", unit_price_minor=50000,
    )
    InventoryItem.objects.create(product=product, location_code=a.code, quantity=3)
    return client, other, operator, a, b, today


def dates(today, **extra):
    return {"start": today.isoformat(), "end": today.isoformat(), **extra}


@pytest.mark.django_db
def test_summary_requires_supervisor_and_assignment(stores):
    client, cashier, operator, a, b, today = stores
    url = "/api/transactional/pos/manage/enterprise-summary/"
    assert cashier.get(url, dates(today)).status_code == 403
    assert client.get(url, dates(today, location_code=b.code)).status_code == 403
    response = client.get(url, dates(today))
    assert response.status_code == 200, response.content
    data = response.json()
    assert len(data["locations"]) == 1
    assert data["totals"]["completed_sales"] == 1
    assert data["totals"]["gross_sales_minor"] == 10000
    assert data["totals"]["cashier_variance_minor"] == -1000

    POSOperatorLocation.objects.create(operator=operator, location=b)
    expanded = client.get(url, dates(today)).json()
    assert len(expanded["locations"]) == 2
    assert expanded["totals"]["gross_sales_minor"] == 100000
    assert client.get(url, dates(today, start="bad")).status_code in (400, 403)


@pytest.mark.django_db
def test_csv_exports_are_scoped_and_formula_safe(stores):
    client, cashier, operator, a, b, today = stores
    url = "/api/transactional/pos/manage/enterprise-export/"
    assert cashier.get(url, dates(today, report_type="daily")).status_code == 403
    assert client.get(url, dates(today, location_code=b.code, report_type="stock")).status_code == 403
    response = client.get(url, dates(today, report_type="stock"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(StringIO(response.content.decode())))
    assert rows[1][0] == "STORE-A"
    assert rows[1][1] == "'=FORMULA()"
    assert rows[1][2] == "'@Excel injection"
    assert rows[1][3] == "3"
    assert "STORE-B" not in response.content.decode()
    closing = client.get(url, dates(today, report_type="closing"))
    assert closing.status_code == 200
    closing_rows = list(csv.reader(StringIO(closing.content.decode())))
    assert closing_rows[1][7] == "-1000"
    assert client.get(url, dates(today, report_type="bad")).status_code == 400
