from django.db import models


class OrderPaymentTypeChoices(models.TextChoices):
    ONLINE = 'online'
    PAY_BY_INVOICE = 'pay-by-invoice'
    CASH_ON_DELIVERY = 'cash-on-delivery'


class PaymentTypeChoices(models.TextChoices):
    ONLINE = 'online'
    CASH = 'cash'


class InvoiceStatusChoices(models.TextChoices):
    """
        define selection fields for status choice
    """
    PLACED = 'Placed'
    UPDATED = 'Updated'
    PARTIALLY_PAID = 'Partially-paid'
    PAYMENT_PENDING = 'Payment-pending'
    PAYMENT_COMPLETED = 'Payment-completed'
    CANCELLED = 'Cancelled'
    CONFIRMED = 'Confirmed'
    PROCESSING = 'Processing'
    READY_TO_DELIVER = 'Ready-to-deliver'
    DELIVERED = 'Delivered'


class DecisionChoices(models.TextChoices):
    """
        define selection fields for decision choice
    """
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'


class PaymentStatusChoices(models.TextChoices):
    """
        define selection fields for decision choice
    """
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'


STATUS_MAPPING = {
    '0': InvoiceStatusChoices.PLACED,
    '1': InvoiceStatusChoices.UPDATED,
    '2': InvoiceStatusChoices.CONFIRMED,
    '3': InvoiceStatusChoices.PARTIALLY_PAID,
    '4': InvoiceStatusChoices.PAYMENT_COMPLETED,
    '5': InvoiceStatusChoices.CANCELLED,
}
