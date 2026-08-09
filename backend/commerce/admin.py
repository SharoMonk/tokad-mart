from django.contrib import admin
from .models import Product, Customer, InventoryLocation, StockBalance, StockMovement, CashierShift, Sale, SaleItem, Payment
for model in [Product,Customer,InventoryLocation,StockBalance,StockMovement,CashierShift,Sale,SaleItem,Payment]: admin.site.register(model)
