from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from transactional.models import (
    InventoryItem, POSLocation, POSOperator, POSOperatorLocation,
    POSOperatorTerminal, POSTerminal, Product,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_demo_seed_is_idempotent_and_does_not_restock_sold_items():
    call_command("seed_demo_pos", "--confirm-demo", stdout=StringIO())
    user = get_user_model().objects.get(username="demo_cashier")
    assert user.is_staff and user.is_active
    assert not user.has_usable_password()
    location = POSLocation.objects.get(code="MAIN")
    terminal = POSTerminal.objects.get(location=location, code="MAIN-01")
    operator = POSOperator.objects.get(user=user)
    assert POSOperatorLocation.objects.filter(operator=operator, location=location).exists()
    assert POSOperatorTerminal.objects.filter(operator=operator, terminal=terminal).exists()
    assert Product.objects.filter(sku__startswith="DEMO-").count() == 4

    item = InventoryItem.objects.get(product__sku="DEMO-RICE-001", location_code="MAIN")
    item.quantity = 17
    item.save(update_fields=["quantity"])

    call_command("seed_demo_pos", "--confirm-demo", stdout=StringIO())
    item.refresh_from_db()
    assert item.quantity == 17
    assert InventoryItem.objects.filter(location_code="MAIN").count() == 4


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_demo_seed_rejected_outside_debug():
    with pytest.raises(CommandError, match="DEBUG=True"):
        call_command("seed_demo_pos", "--confirm-demo", stdout=StringIO())
    assert Product.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_demo_seed_requires_explicit_opt_in():
    with pytest.raises(CommandError, match="confirm-demo"):
        call_command("seed_demo_pos", stdout=StringIO())
    assert POSLocation.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_demo_seed_does_not_elevate_existing_nonstaff_account():
    user = get_user_model().objects.create_user(username="demo_cashier", password="existing-password")
    with pytest.raises(CommandError, match="will not silently elevate"):
        call_command("seed_demo_pos", "--confirm-demo", stdout=StringIO())
    user.refresh_from_db()
    assert not user.is_staff
    assert user.check_password("existing-password")
    assert POSLocation.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_demo_seed_preserves_existing_staff_password():
    user = get_user_model().objects.create_user(
        username="demo_cashier", password="existing-password", is_staff=True
    )
    call_command("seed_demo_pos", "--confirm-demo", stdout=StringIO())
    user.refresh_from_db()
    assert user.check_password("existing-password")
