import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.users.models import Vendor, VendorDeliverySettings

def update_v(name, rating, disc, min_t, max_t, fee, feat=False, pop=False):
    v, _ = Vendor.objects.update_or_create(
        name=name, 
        defaults={
            'rating': rating, 
            'discount_percentage': disc, 
            'is_featured': feat, 
            'is_popular': pop
        }
    )
    ds, _ = VendorDeliverySettings.objects.get_or_create(vendor=v)
    ds.min_delivery_time = min_t
    ds.max_delivery_time = max_t
    ds.base_delivery_fee = fee
    ds.save()
    print(f'Updated {name}')

# Featured Vendors (Admin Selected)
update_v('Nordic Lunch House', 4.8, 15, 15, 30, 29, feat=True)
update_v('Urban Salad Kitchen', 4.7, 25, 15, 25, 32, feat=True)
update_v('Pizza Corner', 4.6, 10, 20, 35, 38, feat=True)

# Popular Vendors (Based on Rating/Orders)
update_v("The Queen's Kebab", 4.9, 20, 10, 35, 35, pop=True)
update_v("Flint's Grill", 3.9, 20, 10, 30, 30, pop=True)
update_v("Brobekk Grill & Pizza", 4.0, 15, 10, 40, 0, pop=True)
