
from logging import getLogger

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.sales.models import AlterCart, Order, SellCart, UserCart
from apps.users.choices import DeviceTypeChoices, RoleTypeChoices
from apps.users.models import Company, UserDeviceToken

# local imports
from backend.celery import app
from backend.fcm import ExFCMNotification
from backend.mail import send_mail_from_template

from .choices import AudienceTypeChoice, NotificationTypeChoice
from .models import Notification, NotificationViewer

User = get_user_model()


@app.task
def notify_company_order_update(id):
    order = Order.objects.get(id=id)
    users = list(order.company.users.filter(
        role__in=[RoleTypeChoices.COMPANY_MANAGER, RoleTypeChoices.COMPANY_OWNER]).values_list('id', flat=True))
    title = "Order status update."
    message = f"Your order (ID: #{order.id}) status has been updated to '{str(order.status).replace('-', ' ')}'."
    send_bulk_notification_and_save(
        user_ids=users,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_STATUS_CHANGED,
        object_id=order.id
    )
    send_order_update_mail(order.company.working_email, title, message, str(order.status).replace('-', ' '))


@app.task
def send_order_update_mail(email, title, message, status):
    """
        send mail to user for sell-order update
    """
    send_mail_from_template(
        'order_status_update.html',
        {
            'year': timezone.now().year,
            'message': message,
            'status': status
        },
        title,
        email
    )


@app.task
def send_admin_mail_for_vendor_product(vendor_name, product_name, product_id):
    """
        send mail to admin for vendor product added
    """
    if product_id:
        message = f"Vendor product '{product_name}' updated by '{vendor_name}'"
    else:
        message = f"New vendor product added by '{vendor_name}', named '{product_name}'"
    send_mail_from_template(
        'vendor_product_added.html',
        {
            'year': timezone.now().year,
            'message': message
        },
        "Vendor Product Updated" if product_id else "Vendor Product Added",
        list(User.objects.filter(
            role__in=[RoleTypeChoices.ADMIN, RoleTypeChoices.SUB_ADMIN]
        ).values_list('email', flat=True))
    )


@app.task
def send_vendor_product_update_mail(email, status, product_name):
    """
        send mail to vendor for vendor product update
    """
    send_mail_from_template(
        'vendor_product_updated.html',
        {
            'year': timezone.now().year,
            'message': f"Your product was {status} by admins. Product name: {product_name}"
        },
        "Vendor Product Updated",
        email
    )


@app.task
def user_cart_added_notification(id):
    cart = SellCart.objects.get(id=id)
    owner_and_managers = cart.added_by.company.users.filter(
        role__in=[RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]
    ).values_list('id', flat=True)
    title = "Staff order request"
    message = f"New food order request has been added by '{cart.added_by.full_name}'"
    send_bulk_notification_and_save(
        user_ids=owner_and_managers,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_CART_ADDED,
        object_id=cart.id
    )
    user_cart_added_mail(cart.added_by.company.working_email, title, message)


@app.task
def user_cart_added_mail(email, title, message):
    """
    """
    send_mail_from_template(
        'staff_order_added.html',
        {
            'year': timezone.now().year,
            'message': message
        },
        title,
        email
    )


@app.task
def user_cart_update_notification(id):
    user_cart = UserCart.objects.get(id=id)
    owner_and_managers = user_cart.added_for.company.users.filter(
        role__in=[RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]
    ).values_list('id', flat=True)
    title = "Staff order updated"
    message = f"'{user_cart.added_for.username}' updated the product '{user_cart.alter_cart.item.name}' for order id '{user_cart.cart.order.id}'"
    send_bulk_notification_and_save(
        user_ids=owner_and_managers,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_CART_UPDATED,
        object_id=user_cart.cart.order.id
    )
    user_cart_update_mail(user_cart.added_for.company.working_email, title, message)


@app.task
def user_cart_update_mail(email, title, message):
    """
    """
    send_mail_from_template(
        'staff_order_update.html',
        {
            'year': timezone.now().year,
            'message': message
        },
        title,
        email
    )


@app.task
def user_cart_update_confirmed_notification(id):
    alter_cart = AlterCart.objects.get(id=id)
    title = "Order update confirmed"
    message = f"'Order update for product '{alter_cart.base.alter_cart.item.name}' for order id '{alter_cart.base.cart.order.id}' was confirmed"
    send_notification_and_save(
        user_id=alter_cart.base.added_for.id,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_CART_UPDATED,
        object_id=alter_cart.base.cart.order.id
    )
    user_cart_update_confirmed_mail(alter_cart.base.added_for.email, title, message)


@app.task
def user_cart_update_confirmed_mail(email, title, message):
    """
    """
    send_mail_from_template(
        'staff_order_update_confirmed.html',
        {
            'year': timezone.now().year,
            'message': message
        },
        title,
        email
    )


@app.task
def user_cart_request_confirmed_notification(user_id, product_name):
    user = User.objects.get(id=user_id)
    title = "Order request confirmed"
    message = f"Your food order request for '{product_name}' has been confirmed."
    send_notification_and_save(
        user_id=user.id,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_CART_CONFIRMED,
    )
    user_cart_request_confirmed_mail(user.email, title, message)


@app.task
def user_cart_request_confirmed_mail(email, title, message):
    """
    """
    send_mail_from_template(
        'staff_order_request_confirmed.html',
        {
            'year': timezone.now().year,
            'message': message
        },
        title,
        email
    )


@app.task
def notify_vendor_product(id):
    cart = SellCart.objects.get(id=id)
    vendor = cart.item.vendor
    if vendor.users.last():
        send_notification_and_save(
            user_id=vendor.users.last().id,
            title="Product added",
            message=f"Company '{cart.order.company.name}' ordered your product -> '{cart.item.name}'",
            n_type=NotificationTypeChoice.VENDOR_PRODUCT_ORDERED,
            object_id=cart.id
        )


@app.task
def notify_company_registration(id):
    company = Company.objects.get(id=id)
    send_admin_notification_and_save(
        title="Company registration",
        message=f"New company '{company.name}' has been registered",
        n_type=NotificationTypeChoice.COMPANY_REGISTERED,
        object_id=company.id
    )


@app.task
def send_notification_and_save(user_id, title, message, n_type, object_id=None):
    user = User.objects.get(id=user_id)
    token = getattr(user, 'device_tokens', None)
    notification = Notification.objects.create(
        # user=instance.sender,
        title=title,
        message=message,
        notification_type=n_type,
        object_id=object_id,
        audience_type=AudienceTypeChoice.USERS
    )
    notification.sent_on = timezone.now()
    notification.save()
    notification.users.add(user)
    token = token.filter(is_current=True).last()
    if token:
        send_user_notification.delay(
            token.device_token, notification.title, notification.message, notification.notification_type)
    else:
        getLogger().error("No user device token found.")


@app.task
def send_bulk_notification_and_save(user_ids, title, message, n_type=NotificationTypeChoice.ALERT, audience_type=AudienceTypeChoice.USERS, object_id=None):
    users = User.objects.filter(id__in=user_ids)
    tokens = list(UserDeviceToken.objects.filter(
        user__in=users).order_by('device_token').values_list('device_token', flat=True).distinct())
    notification = Notification.objects.create(
        # user=instance.sender,
        title=title,
        message=message,
        notification_type=n_type,
        object_id=object_id,
        audience_type=audience_type
    )
    notification.sent_on = timezone.now()
    notification.save()
    notification.users.add(*users)
    if tokens:
        send_bulk_notification(title, message, tokens, n_type)
    else:
        getLogger().error("No user device token found.")


@app.task
def send_admin_notification_and_save(
        title, message, n_type=NotificationTypeChoice.ALERT, audience_type=AudienceTypeChoice.ADMINS, object_id=None
):
    user_tokens = UserDeviceToken.objects.filter(user__is_staff=True, user__is_active=True)
    tokens = list(set(list(user_tokens.values_list('device_token', flat=True).distinct())))
    admins = list(set(list(user_tokens.values_list('user__email').distinct())))
    users = User.objects.filter(email__in=[user[0] for user in admins])
    notification = Notification.objects.create(
        # user=instance.sender,
        title=title,
        message=message,
        notification_type=n_type,
        object_id=object_id,
        audience_type=audience_type
    )
    notification.sent_on = timezone.now()
    notification.save()
    notification.users.add(*users)
    if tokens:
        send_bulk_notification(title, message, tokens, n_type)
    else:
        getLogger().error("No admin device token found.")


@app.task
def send_admin_sell_order_mail(company_id, orders):
    print(100, orders)
    # orders = Order.objects.filter(id__in=orders)
    # print(101, orders)
    company = Company.objects.get(id=company_id)
    send_mail_from_template(
        'admin_sell_order_mail.html', {
            'message': f"New orders placed by '{company.name}'", 'orders': orders, 'year': timezone.now().year
        }, "New Order placed", list(User.objects.filter(
            role__in=[RoleTypeChoices.ADMIN, RoleTypeChoices.SUB_ADMIN]
        ).values_list('email', flat=True))
    )


@app.task
def notify_order_placed(id, orders=[]):
    company = Company.objects.get(id=id)
    title = "Order Placed"
    message = "Your orders have been placed successfully."
    users = list(company.users.filter(
        role__in=[RoleTypeChoices.COMPANY_MANAGER, RoleTypeChoices.COMPANY_OWNER]).values_list('id', flat=True))
    send_bulk_notification_and_save(
        user_ids=users,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_PLACED,
        object_id=None
    )
    orders = Order.objects.filter(id__in=orders)
    send_mail_from_template(
        'sell_order_mail.html', {'message': message, 'orders': orders, 'year': timezone.now().year},
        title, company.working_email
    )


@app.task
def notify_employee_cart(id):
    user_cart = UserCart.objects.get(id=id)
    users = list(User.objects.filter(id=user_cart.added_for.id).values_list('id', flat=True))
    title = "Food order added."
    message = f"Food has been ordered for you. Order: #{user_cart.cart.order.id}; Product: {user_cart.cart.item.name}"
    send_bulk_notification_and_save(
        user_ids=users,
        title=title,
        message=message,
        n_type=NotificationTypeChoice.ORDER_STATUS_CHANGED,
        object_id=user_cart.cart.order.id
    )
    notify_employee_cart_mail(user_cart.cart.order.company.working_email, title, message)


@app.task
def notify_employee_cart_mail(email, title, message):
    """
        send mail to user for sell-order cart added
    """
    send_mail_from_template(
        'order_employee_cart.html',
        {
            'year': timezone.now().year,
            'message': message,
        },
        title,
        email
    )


@app.task
def send_user_notification(token, title, message, notification_type):
    """
        send notification to single user
    """
    fcm = ExFCMNotification(
        title=title,
        message=message,
        token=token,
        notification_type=notification_type
    )
    try:
        fcm.send_notification()
    except Exception as e:
        getLogger().error(e)


def divide_chunks(ls, n):
    """
        take a list and return the list to n length
    """
    for i in range(0, len(ls), n):
        yield ls[i: i + n]


@app.task
def send_bulk_notification(title, msg, tokens, notification_type):
    """
        divide recipients into chunks for limit 500
    """
    for chunk in divide_chunks(tokens, 500):
        send_chunk_notifications.delay(title, msg, chunk, notification_type)


@app.task
def send_chunk_notifications(title, msg, tokens, notification_type):
    """
        send notification to multiple users by their tokens
    """
    print("Start", timezone.now(), flush=True)
    try:
        ExFCMNotification(title, msg, None, notification_type).send_bulk_notification(tokens)
    except Exception as e:
        print(e)
        getLogger().error(f"{e}")
    print("End", timezone.now(), flush=True)


@app.task
def send_user_bulk_notification(title, message, tokens, notification_type):
    """
        take required arguments and proceed for sending notification
    """
    print(tokens)
    send_bulk_notification(title, message, tokens, notification_type)


@app.task
def send_scheduled_notifications():
    """
        check for notifications if scheduled and not sent
    """
    now = timezone.now()
    start = now.replace(second=0, microsecond=0)
    end = now.replace(second=59)
    notifications = Notification.objects.filter(
        scheduled_on__gte=start, scheduled_on__lte=end, sent_on__isnull=True)
    print(notifications)
    for item in notifications:
        users = item.users.all()
        user_tokens = UserDeviceToken.objects.filter(user__in=users)
        tokens = list(set(list(user_tokens.values_list('device_token', flat=True).distinct())))
        send_user_bulk_notification.delay(item.title, item.message, tokens, item.notification_type)
        item.sent_on = now
        item.save()


@app.task
def send_admin_notification(instance, created):
    user_tokens = UserDeviceToken.objects.filter(user__is_staff=True, user__is_active=True,
                                                 device_type=DeviceTypeChoices.WEB)
    tokens = list(set(list(user_tokens.values_list('device_token', flat=True).distinct())))
    admins = list(set(list(user_tokens.values_list('user__email').distinct())))
    admins = User.objects.filter(email__in=[user[0] for user in admins])
    if admins:
        title = "New order added" if created else "Order updated",
        message = "New order added" if created else "Order updated" + " and waiting for approval.",
        notification_type = NotificationTypeChoice.ORDER_PLACED
        if tokens:
            send_user_bulk_notification(title, message, tokens, notification_type)
        else:
            getLogger().error("No admin device token found.")
    else:
        getLogger().error("No admin found for receiving notification.")


@app.task
def make_seen_all_notifications(user_id):
    user = User.objects.get(id=user_id)
    if user.is_admin:
        notifications = Notification.objects.filter(audience_type=AudienceTypeChoice.ADMINS)
        read = NotificationViewer.objects.filter(notification__in=notifications).values_list('notification', flat=True)
    else:
        notifications = Notification.objects.filter(users=user, sent_on__lte=timezone.now())
        read = NotificationViewer.objects.filter(
            notification__in=notifications, user=user).values_list('notification', flat=True)
    for ins in notifications.exclude(id__in=read):
        obj = NotificationViewer.objects.get_or_create(notification=ins, user=user)[0]
        obj.view_count += 1
        obj.save()
