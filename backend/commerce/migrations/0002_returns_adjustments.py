from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from decimal import Decimal

class Migration(migrations.Migration):
    dependencies=[('commerce','0001_initial')]
    operations=[
        migrations.CreateModel(name='SaleReturn',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('number',models.CharField(max_length=32,unique=True)),('total',models.DecimalField(decimal_places=2,max_digits=14)),('reason',models.CharField(blank=True,default='',max_length=255)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('cashier',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),('location',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='commerce.inventorylocation')),('sale',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='returns',to='commerce.sale'))]),
        migrations.CreateModel(name='SaleReturnItem',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('quantity',models.DecimalField(decimal_places=3,max_digits=14)),('refund_amount',models.DecimalField(decimal_places=2,max_digits=14)),
            ('return_document',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='items',to='commerce.salereturn')),('sale_item',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='commerce.saleitem'))]),
        migrations.CreateModel(name='InventoryAdjustment',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('number',models.CharField(max_length=32,unique=True)),('quantity_delta',models.DecimalField(decimal_places=3,max_digits=14)),('reason',models.CharField(max_length=255)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),('location',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='commerce.inventorylocation')),('product',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='commerce.product'))]),
    ]
