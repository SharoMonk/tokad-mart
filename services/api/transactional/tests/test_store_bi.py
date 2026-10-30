"""BI endpoints honor store scope and derive products from completed sales."""
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product, Sale, SaleLine,
)


@pytest.mark.django_db
def test_bi_insights_scoped_completed_sales_and_current_stock():
    loc = POSLocation.objects.create(code="BI", name="BI test")
    other = POSLocation.objects.create(code="OTHER-BI", name="Other")
    terminal = POSTerminal.objects.create(location=loc, code="T1", name="Till")
    user = get_user_model().objects.create_user("bi-supervisor", is_staff=True)
    op = POSOperator.objects.create(user=user, role=POSOperator.Role.SUPERVISOR)
    POSOperatorLocation.objects.create(operator=op, location=loc)
    POSOperatorTerminal.objects.create(operator=op, terminal=terminal)
    client = Client()
    client.force_login(user)
    product = Product.objects.create(sku="BI-RICE", name="Rice", unit_price_minor=10000)
    InventoryItem.objects.create(product=product, location_code=loc.code, quantity=2)
    today = timezone.localdate()
    sale = Sale.objects.create(
        reference=uuid4(), location_code=loc.code, currency="NGN",
        status=Sale.Status.COMPLETED, subtotal_minor=30000,
        total_minor=30000, completed_at=timezone.now(),
    )
    SaleLine.objects.create(
        sale=sale, product=product, sku_snapshot=product.sku,
        name_snapshot=product.name, quantity=3,
        unit_price_minor=10000, line_total_minor=30000,
    )
    Sale.objects.create(
        reference=uuid4(), location_code=other.code, currency="NGN",
        status=Sale.Status.COMPLETED, subtotal_minor=90000,
        total_minor=90000, completed_at=timezone.now(),
    )
    url = "/api/transactional/pos/manage/bi-insights/"
    params = {
        "location_code": loc.code, "terminal_code": terminal.code,
        "start": today.isoformat(), "end": today.isoformat(), "threshold": "5",
    }
    response = client.get(url, params)
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["daily_sales"][0]["gross_minor"] == 30000
    assert data["top_products"][0]["units"] == 3
    assert data["low_stock"][0]["stock"] == 2
    assert client.get(url, {**params, "location_code": other.code}).status_code == 403
    assert client.get(url, {**params, "threshold": "-1"}).status_code == 400
