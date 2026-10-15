import pytest
from django.test import Client
from django.contrib.auth import get_user_model

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product, Sale, SaleLine,
)


@pytest.mark.django_db
def test_catalog_and_scope_only_expose_operator_assigned_location():
    user = get_user_model().objects.create_user("catalog-cashier", password="test-password", is_staff=True)
    location = POSLocation.objects.create(code="MAIN", name="Main")
    terminal = POSTerminal.objects.create(location=location, code="T1", name="Terminal 1")
    operator = POSOperator.objects.create(user=user)
    POSOperatorLocation.objects.create(operator=operator, location=location)
    POSOperatorTerminal.objects.create(operator=operator, terminal=terminal)
    item = Product.objects.create(sku="CAT1", name="Milo", currency="NGN", unit_price_minor=125000)
    InventoryItem.objects.create(product=item, location_code="MAIN", quantity=5)
    client = Client()
    client.force_login(user)

    scope = client.get("/api/transactional/pos/scope/")
    assert scope.status_code == 200
    assert scope.json()["locations"][0]["terminals"][0]["code"] == "T1"

    result = client.get("/api/transactional/pos/catalog/", {
        "location_code": "MAIN", "terminal_code": "T1", "q": "Mil"
    })
    assert result.status_code == 200
    assert result.json()["products"][0]["unit_price_minor"] == 125000
    assert result.json()["products"][0]["stock"] == 5

    forbidden = client.get("/api/transactional/pos/catalog/", {
        "location_code": "OTHER", "terminal_code": "T1", "q": "Mil"
    })
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_catalog_requires_authenticated_operator():
    response = Client().get("/api/transactional/pos/catalog/", {
        "location_code": "MAIN", "terminal_code": "T1", "q": "Mil"
    })
    assert response.status_code in (401, 403)
