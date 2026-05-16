import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.scm.models import Product
from apps.users.models import Vendor

v = Vendor.objects.first()
if not v:
    print("No vendor found, please create one first.")
else:
    def add_p(name, rating, count, badge, price, pop=False, feat=False):
        p, _ = Product.objects.update_or_create(
            name=name, 
            defaults={
                'average_rating': rating, 
                'orders_count': count, 
                'badge': badge, 
                'is_popular': pop, 
                'is_featured': feat, 
                'vendor': v,
                'description': name,
                'status': 'APPROVED',
                'price_with_tax': price,
                'tax_percent': 15  # Default tax
            }
        )
        print(f'Added {name}')

    # Popular Products
    add_p('Morning Croissant Box', 4.8, 120, 'Freshly baked', 150, pop=True)
    add_p('Executive Breakfast Tray', 4.7, 85, 'Office favorite', 250, pop=True)
    add_p('Smokehouse Rib Platter', 4.9, 200, 'Top rated', 450, pop=True)
    add_p('Pizza Lunch Duo', 4.6, 150, 'Shareable', 300, pop=True)

    # Featured Products
    add_p('Garden Salad Crate', 4.7, 90, 'Light and fresh', 180, feat=True)
    add_p('Asian Noodle Office Box', 4.5, 110, 'Staff pick', 220, feat=True)
