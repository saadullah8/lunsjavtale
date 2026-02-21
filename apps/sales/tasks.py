import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F

from apps.notifications.tasks import notify_employee_cart, notify_vendor_product
from apps.sales.choices import InvoiceStatusChoices, PaymentStatusChoices
from apps.sales.models import OnlinePayment, Order, OrderPayment, SellCart, UserCart

# local imports
from backend.celery import app

User = get_user_model()


def get_payment_info(payment_id):
    try:
        online_payment = OnlinePayment.objects.get(id=payment_id)
        session_state = online_payment.session_data.get('sessionState')
    except Exception:
        return None
    if session_state == "PaymentSuccessful":
        return online_payment
    elif session_state == "PaymentTerminated":
        return None
    url = f"{settings.PAYMENT_SITE_URL}/checkout/v3/session/{payment_id}/"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Vipps-System-Name": settings.VIPPS_SYSTEM_NAME,
        "Vipps-System-Version": settings.VIPPS_SYSTEM_VERSION,
        "Vipps-System-Plugin-Name": settings.VIPPS_SYSTEM_PLUGIN_NAME,
        "Vipps-System-Plugin-Version": settings.VIPPS_SYSTEM_PLUGIN_VERSION,
        "client_id": settings.VIPPS_CLIENT_ID,
        "client_secret": settings.VIPPS_CLIENT_SECRET,
        "Ocp-Apim-Subscription-Key": settings.VIPPS_SUBSCRIPTION_KEY,
        "Merchant-Serial-Number": settings.VIPPS_MERCHANT_SERIAL_NUMBER,
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("Status Code", response.status_code)
        online_payment.session_data = {**response.json(), **{'payment_id': online_payment.order_payment.id}}
        online_payment.save()
        if online_payment.session_data.get('sessionState') == "PaymentTerminated":
            online_payment.order_payment.status = PaymentStatusChoices.CANCELLED
            online_payment.order_payment.save()
        if online_payment.session_data.get('sessionState') == "PaymentSuccessful":
            order_payment = online_payment.order_payment
            order_payment.status = PaymentStatusChoices.COMPLETED
            order_payment.save()
            if not order_payment.deduction:
                make_previous_payment.delay(order_payment.id)
    else:
        print("Status Code", response.status_code)
        print("JSON Response ", response.json())
    return online_payment


def make_online_payment(payment_id):
    payment = OrderPayment.objects.get(id=payment_id)
    online_payment = OnlinePayment.objects.create(order_payment=payment)

    url = f"{settings.PAYMENT_SITE_URL}/checkout/v3/session/"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Vipps-System-Name": settings.VIPPS_SYSTEM_NAME,
        "Vipps-System-Version": settings.VIPPS_SYSTEM_VERSION,
        "Vipps-System-Plugin-Name": settings.VIPPS_SYSTEM_PLUGIN_NAME,
        "Vipps-System-Plugin-Version": settings.VIPPS_SYSTEM_PLUGIN_VERSION,
        "client_id": settings.VIPPS_CLIENT_ID,
        "client_secret": settings.VIPPS_CLIENT_SECRET,
        "Ocp-Apim-Subscription-Key": settings.VIPPS_SUBSCRIPTION_KEY,
        "Merchant-Serial-Number": settings.VIPPS_MERCHANT_SERIAL_NUMBER,
    }
    data = {
        "merchantInfo": {
            "callbackUrl": f"{settings.SITE_URL}/{settings.PAYMENT_CALLBACK_EXTENSION}/?ref={online_payment.id}",
            "returnUrl": f"{settings.SITE_URL}/{settings.PAYMENT_CALLBACK_EXTENSION}/?ref={online_payment.id}",
            "callbackAuthorizationToken": "",
            "termsAndConditionsUrl": f"{settings.SITE_URL}/dadmin"
        },
        "transaction": {
            "amount": {
                "value": int(float(payment.paid_amount) * 100),
                "currency": "NOK"
            },
            "reference": f"{online_payment.id}",
            "paymentDescription": payment.company.working_email
        }
    }

    response = requests.post(url, headers=headers, json=data)

    print("Status Code", response.status_code)
    if response.status_code == 200:
        print("JSON Response ", response.json())
        online_payment.request_headers = headers
        online_payment.request_data = data
        online_payment.response_data = response.json()
        online_payment.save()
        trigger_payment.delay(online_payment.id)
        if online_payment.response_data.get('checkoutFrontendUrl') and online_payment.response_data.get('token'):
            return f"{online_payment.response_data.get('checkoutFrontendUrl')}?token={online_payment.response_data.get('token')}"
        return None
    else:
        online_payment.response_data = response.json()
        online_payment.save()
        print("Error JSON Response ", response.json())
    return None


@app.task
def trigger_payment(id):
    # sleep(300)  # seconds
    get_payment_info(id)


@app.task
def notify_user_carts(ids):
    # obj = Order.objects.get(id=id)
    carts = SellCart.objects.filter(id__in=ids)
    # for cart in obj.order_carts.all():
    for cart in carts:
        add_user_carts(cart.id)
        if cart.item.vendor:
            # vendor = cart.item.vendor
            # vendor.sold_amount += cart.total_price_with_tax
            # vendor.save()
            notify_vendor_product(cart.id)


@app.task
def vendor_sold_amount_calculation(id):
    obj = Order.objects.get(id=id)
    carts = SellCart.objects.filter(order=obj, item__vendor__isnull=False)
    for cart in carts:
        if cart.item.vendor:
            vendor = cart.item.vendor
            vendor.sold_amount += cart.total_price_with_tax
            vendor.save()


@app.task
def add_user_carts(id):
    cart = SellCart.objects.get(id=id)
    for user in cart.added_for.all():
        user_cart, c = UserCart.objects.get_or_create(added_for=user, cart=cart)
        # notify staffs
        if c:
            notify_employee_cart(user_cart.id)
        if cart.order.statuses.filter(status=InvoiceStatusChoices.PAYMENT_COMPLETED).exists():
            user_cart.paid_amount = cart.price_with_tax * cart.order.company_allowance / 100
            user_cart.save()
        user_cart.ingredients.add(*cart.ingredients.exclude(id__in=user.allergies.values_list('id', flat=True)))
    UserCart.objects.filter(cart=cart).exclude(added_for__in=cart.added_for.all()).delete()


@app.task
def make_previous_payment(id):
    obj = OrderPayment.objects.get(id=id)
    if not obj.deduction:
        obj.deduction = []
    paid_amount = obj.paid_amount
    if obj.user_carts.exists():
        for user_cart in obj.user_carts.all().order_by('cart__order__created_on'):
            due = (user_cart.cart.price_with_tax * (100 - user_cart.cart.order.company_allowance) / 100) - user_cart.paid_amount
            if paid_amount >= due:
                user_cart.paid_amount = user_cart.cart.price_with_tax * (100 - user_cart.cart.order.company_allowance) / 100
                user_cart.save()
                order = user_cart.cart.order
                order.paid_amount += due
                order.save()
                obj.deduction.append({'cart': user_cart.id, 'amount': str(due)})
                obj.save()
                paid_amount -= due
            else:
                user_cart.paid_amount += paid_amount
                user_cart.save()
                order = user_cart.cart.order
                order.paid_amount += paid_amount
                order.save()
                obj.deduction.append({'cart': user_cart.id, 'amount': str(paid_amount)})
                obj.save()
                paid_amount -= paid_amount
                break
    elif obj.payment_for:
        user_carts = obj.payment_for.cart_items.annotate(
            c_due=F('cart__price_with_tax') * (100 - F('cart__order__company_allowance')) / 100 - F('paid_amount')
        ).filter(c_due__gt=0)
        for user_cart in user_carts.order_by('cart__order__created_on'):
            obj.user_carts.add(user_cart)
            due = (user_cart.cart.price_with_tax * (100 - user_cart.cart.order.company_allowance) / 100) - user_cart.paid_amount
            if paid_amount >= due:
                user_cart.paid_amount = user_cart.cart.price_with_tax * (100 - user_cart.cart.order.company_allowance) / 100
                user_cart.save()
                order = user_cart.cart.order
                order.paid_amount += due
                order.save()
                obj.deduction.append({'cart': user_cart.id, 'amount': str(due)})
                obj.save()
                paid_amount -= due
            else:
                user_cart.paid_amount += paid_amount
                user_cart.save()
                order = user_cart.cart.order
                order.paid_amount += paid_amount
                order.save()
                obj.deduction.append({'cart': user_cart.id, 'amount': str(paid_amount)})
                obj.save()
                paid_amount -= paid_amount
                break
    else:
        company = obj.company
        total_due = 0
        if obj.orders.exists():
            for order in obj.orders.all().order_by('created_on'):
                # final_price = order.final_price * order.company_allowance / 100
                # if paid_amount >= final_price - order.paid_amount:
                due = order.company_due_amount
                if paid_amount >= due:
                    total_due += due
                    if order.status == InvoiceStatusChoices.PAYMENT_PENDING:
                        order.status = InvoiceStatusChoices.PAYMENT_COMPLETED
                    order.paid_amount += due
                    order.save()
                    obj.deduction.append({'order': order.id, 'amount': str(due)})
                    obj.save()
                    paid_amount -= due
                else:
                    order.paid_amount += paid_amount
                    order.save()
                    obj.deduction.append({'order': order.id, 'amount': str(paid_amount)})
                    obj.save()
                    paid_amount -= paid_amount
                    total_due += paid_amount
                    break
        else:
            orders = obj.company.orders.annotate(
                c_due=F('final_price') - F('paid_amount')
            ).filter(c_due__gt=0)
            for order in orders.order_by('created_on'):
                if order.company_due_amount > 0:
                    obj.orders.add(order)
                    # final_price = order.final_price * order.company_allowance / 100
                    due = order.company_due_amount
                    if paid_amount >= due:
                        if order.status == InvoiceStatusChoices.PAYMENT_PENDING:
                            order.status = InvoiceStatusChoices.PAYMENT_COMPLETED
                        order.paid_amount += due
                        order.save()
                        obj.deduction.append({'order': order.id, 'amount': str(due)})
                        obj.save()
                        paid_amount -= due
                        total_due += due
                    else:
                        order.paid_amount += paid_amount
                        order.save()
                        obj.deduction.append({'order': order.id, 'amount': str(paid_amount)})
                        obj.save()
                        total_due += paid_amount
                        paid_amount -= paid_amount
                        break

        company.paid_amount += total_due
        company.save()
