import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.sales.models import Order, ClientOrder, SellCart
from apps.users.models import Vendor

print("=== LATEST CLIENT ORDERS ===")
for co in ClientOrder.objects.all().order_by('-id')[:5]:
    print(f"ClientOrder ID: {co.id}, Status: {co.status}, Grand Total: {co.grand_total}, Linked Order: {co.order_id if co.order else 'None'}, Email: {co.email}")

print("\n=== LATEST CORPORATE ORDERS ===")
for o in Order.objects.all().order_by('-id')[:5]:
    print(f"Order ID: {o.id}, Status: {o.status}, Final Price: {o.final_price}, Created By: {o.created_by.email if o.created_by else 'None'}")
    # Show SellCarts for this order
    carts = SellCart.objects.filter(order=o)
    for c in carts:
        print(f"  -> Cart ID: {c.id}, Product: {c.item.title or c.item.name}, Qty: {c.quantity}, Price: {c.price}, PriceWithTax: {c.price_with_tax}, TotalPriceWithTax: {c.total_price_with_tax}")

print("\n=== VENDORS ===")
for v in Vendor.objects.all():
    print(f"Vendor Name: {v.name}, Sold Amount: {v.sold_amount}, Balance: {v.balance}")
