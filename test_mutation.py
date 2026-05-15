import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from backend.schema import schema
from graphene.test import Client

query = '''
mutation {
  placeClientOrder(
    vendorId: "9", 
    customerType: "Corporate",
    email: "test@test.com",
    phone: "123",
    deliveryAddressStr: "123",
    invoiceAddressStr: "123",
    items: [{ product: "1", quantity: 1 }]
  ) {
    success
    message
  }
}
'''
client = Client(schema)
try:
    result = client.execute(query)
    print('RESULT:', result)
except Exception as e:
    import traceback
    traceback.print_exc()
