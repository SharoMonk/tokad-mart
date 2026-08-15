from django.urls import path

from .views import health, pos_cash_sale


urlpatterns = [
    path(
        "health/",
        health,
        name="transactional-health",
    ),
    path(
        "pos/sales/",
        pos_cash_sale,
        name="pos-cash-sale",
    ),
]