from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.bases.models import BaseModel, BaseWithoutID, SoftDeletion
from apps.sales.choices import (
    DecisionChoices,
    InvoiceStatusChoices,
    OrderPaymentTypeChoices,
    PaymentStatusChoices,
    PaymentTypeChoices,
)


class PaymentMethod(BaseWithoutID, SoftDeletion):
    user = models.ForeignKey(
        to='users.User', on_delete=models.DO_NOTHING, related_name='payment_methods'
    )
    card_holder_name = models.CharField(max_length=128)
    card_number = models.CharField(max_length=128)
    CVV = models.CharField(max_length=6)
    expiry = models.DateField()
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_payment_methods"  # define table name for database
        ordering = ['-id']  # define default order as id in descending

    def save(self, *args, **kwargs):
        if self.is_default:
            self.user.payment_methods.exclude(id=self.pk).update(is_default=False)
        super(PaymentMethod, self).save(*args, **kwargs)


class SellCartManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SellCart(BaseWithoutID, SoftDeletion):
    order = models.ForeignKey(
        to='Order', on_delete=models.DO_NOTHING, related_name='order_carts', blank=True, null=True
    )

    added_by = models.ForeignKey(
        to='users.User', on_delete=models.SET_NULL, related_name='added_carts', blank=True, null=True
    )

    item = models.ForeignKey(
        to='scm.Product', on_delete=models.DO_NOTHING, related_name='product_carts'
    )
    date = models.DateField()
    added_for = models.ManyToManyField(
        to='users.User', blank=True
    )
    cancelled_by = models.ManyToManyField(
        to='users.User', blank=True, related_name="cancelled_carts"
    )
    quantity = models.PositiveIntegerField(
        db_index=True, default=1, validators=[MinValueValidator(1)]
    )
    cancelled = models.PositiveIntegerField(default=0)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    price_with_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    total_price_with_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    ingredients = models.ManyToManyField(
        to='scm.Ingredient', help_text="Allergies", blank=True
    )
    is_requested = models.BooleanField(default=False)
    request_status = models.CharField(
        max_length=32, choices=DecisionChoices.choices, default=DecisionChoices.PENDING
    )

    objects = SellCartManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_sell_carts"  # define table name for database

    def save(self, *args, **kwargs):
        self.total_price = self.price * self.ordered_quantity
        self.total_price_with_tax = self.price_with_tax * self.ordered_quantity
        super(SellCart, self).save(*args, **kwargs)

    @property
    def ordered_quantity(self):
        return self.quantity - self.cancelled

    @property
    def due_amount(self):
        paid_amount = self.users.aggregate(paid=models.Sum('paid_amount'))['paid'] or 0
        return self.total_price_with_tax - paid_amount


class UserCart(BaseWithoutID):
    cart = models.ForeignKey(
        to=SellCart, on_delete=models.DO_NOTHING, related_name='users'
    )
    added_for = models.ForeignKey(
        to='users.User', on_delete=models.DO_NOTHING, related_name='cart_items'
    )
    payment_type = models.CharField(
        max_length=16, choices=OrderPaymentTypeChoices.choices, default=OrderPaymentTypeChoices.PAY_BY_INVOICE
    )
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    ingredients = models.ManyToManyField(
        to='scm.Ingredient', help_text="Allergies", blank=True
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_carts"  # define table name for database

    @property
    def is_full_paid(self):
        return self.cart.price_with_tax <= self.paid_amount

    @property
    def due_amount(self):
        item_price = self.cart.price_with_tax - (self.cart.price_with_tax * self.cart.order.company_allowance / 100)
        return item_price - self.paid_amount


class AlterCart(BaseWithoutID):
    base = models.OneToOneField(
        to=UserCart, on_delete=models.CASCADE, related_name='alter_cart'
    )
    previous_cart = models.ForeignKey(
        to=SellCart, on_delete=models.DO_NOTHING, related_name='previous_used_carts'
    )
    item = models.ForeignKey(
        to='scm.Product', on_delete=models.DO_NOTHING, related_name='alter_carts'
    )
    status = models.CharField(max_length=32, choices=DecisionChoices.choices, default=DecisionChoices.PENDING)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_alter_carts"  # define table name for database


class OrderManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Order(BaseWithoutID, SoftDeletion):
    company = models.ForeignKey(
        to='users.Company', on_delete=models.DO_NOTHING, related_name='orders'
    )
    shipping_address = models.ForeignKey(
        to='users.Address', on_delete=models.SET_NULL, related_name='orders', blank=True, null=True
    )
    created_by = models.ForeignKey(to='users.User', on_delete=models.DO_NOTHING, related_name='created_orders')
    note = models.TextField(blank=True, null=True)
    coupon = models.ForeignKey('users.Coupon', on_delete=models.DO_NOTHING, blank=True, null=True)
    payment_type = models.CharField(
        max_length=16, choices=OrderPaymentTypeChoices.choices, default=OrderPaymentTypeChoices.PAY_BY_INVOICE
    )
    delivery_date = models.DateField()
    company_allowance = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0
    )
    shipping_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    actual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="price adding vat & discount",
        default=0
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="price adding vat & discount",
        default=0
    )
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    status = models.CharField(
        max_length=32, choices=InvoiceStatusChoices.choices, default=InvoiceStatusChoices.PLACED
    )
    is_full_paid = models.BooleanField(default=False)
    is_checked = models.BooleanField(default=False)

    objects = OrderManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_orders"  # define table name for database
        ordering = ['-id']  # define default order as id in descending

    def save(self, *args, **kwargs):
        if self.pk and self.order_carts.exists():
            self.actual_price = self.order_carts.aggregate(tot=models.Sum('total_price'))['tot']
            self.final_price = self.order_carts.aggregate(
                tot=models.Sum('total_price_with_tax'))['tot'] - self.discount_amount + self.shipping_charge
            self.is_full_paid = self.company_due_amount <= self.paid_amount
        super(Order, self).save(*args, **kwargs)

    @property
    def due_amount(self):
        return self.final_price - self.paid_amount

    @property
    def company_due_amount(self):
        return (self.final_price - self.employee_due_amount) - self.paid_amount

    @property
    def employee_due_amount(self):
        paid_amount = UserCart.objects.filter(
            cart__in=self.order_carts.all()
        ).aggregate(paid=models.Sum('paid_amount'))['paid'] or 0
        staff_amount = 0
        for cart in self.order_carts.all():
            staff_amount += (cart.price_with_tax * (100 - self.company_allowance) / 100) * cart.added_for.count()
        return staff_amount - paid_amount

    # def get_payment_status(self, final_price, company_allowance, paid_amount):
    #     return (final_price * company_allowance / 100) <= paid_amount


class BillingAddress(BaseWithoutID):
    """
        billing address information will be stored here by address type.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="billing_address"
    )
    first_name = models.CharField(max_length=128, null=True, blank=True)
    last_name = models.CharField(max_length=128, null=True, blank=True)
    address = models.TextField()
    sector = models.CharField(max_length=128, blank=True, null=True)
    country = models.CharField(max_length=128, blank=True, null=True)
    phone = models.CharField(max_length=15, null=True, blank=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_billing_addresses"  # define table name for database
        verbose_name_plural = "Billing addresses"


class OrderStatus(models.Model):
    order = models.ForeignKey(
        to=Order, on_delete=models.SET_NULL, related_name='statuses', blank=True, null=True
    )
    status = models.CharField(
        max_length=32, choices=InvoiceStatusChoices.choices, default=InvoiceStatusChoices.PLACED
    )
    note = models.TextField(null=True, blank=True)
    created_on = models.DateTimeField(
        auto_now_add=True
    )  # object creation time. will automatically generate

    class Meta:
        db_table = f"{settings.DB_PREFIX}_order_statuses"  # define table name for database

    def save(self, *args, **kwargs):
        super(OrderStatus, self).save(*args, **kwargs)
        self.order.status = self.order.statuses.latest('created_on').status
        self.order.note = self.order.statuses.latest('created_on').note
        self.order.save()


# class UserCartStatus(models.Model):
#     user_cart = models.ForeignKey(
#         to=UserCart, on_delete=models.SET_NULL, related_name='statuses'
#     )
#     status = models.CharField(
#         max_length=32, choices=InvoiceStatusChoices.choices, default=InvoiceStatusChoices.PLACED
#     )
#     created_on = models.DateTimeField(
#         auto_now_add=True
#     )  # object creation time. will automatically generate
#
#     class Meta:
#         db_table = f"{settings.DB_PREFIX}_user_cart_statuses"  # define table name for database


class OrderPaymentManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class OrderPayment(BaseWithoutID, SoftDeletion):
    orders = models.ManyToManyField(
        to=Order, blank=True
    )
    user_carts = models.ManyToManyField(
        to=UserCart, blank=True
    )
    company = models.ForeignKey(
        to='users.Company', on_delete=models.SET_NULL, related_name='payments', null=True
    )
    payment_for = models.ForeignKey(
        to='users.User', on_delete=models.SET_NULL, related_name='payments', null=True, blank=True
    )
    payment_type = models.CharField(
        max_length=16, choices=PaymentTypeChoices.choices, default=PaymentTypeChoices.CASH
    )
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    note = models.TextField(blank=True, null=True)
    payment_info = models.JSONField(blank=True, null=True)
    deduction = models.JSONField(blank=True, null=True, default=list)
    created_by = models.ForeignKey(to='users.User', on_delete=models.DO_NOTHING, related_name='created_payments')
    status = models.CharField(
        max_length=32, choices=PaymentStatusChoices.choices, default=PaymentStatusChoices.PENDING)
    is_checked = models.BooleanField(default=False)

    objects = OrderPaymentManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_order_payments"  # define table name for database


class OnlinePayment(BaseModel):
    order_payment = models.ForeignKey(
        to=OrderPayment, on_delete=models.DO_NOTHING
    )
    request_headers = models.JSONField(blank=True, null=True)
    request_data = models.JSONField(blank=True, null=True)
    response_data = models.JSONField(blank=True, null=True)
    session_data = models.JSONField(blank=True, null=True, default=dict)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_online_payments"  # define table name for database
        ordering = ['-created_on']  # define default order as id in descending

    @property
    def status(self):
        return self.session_data.get('sessionState', "")


class ProductRating(BaseWithoutID):
    added_by = models.ForeignKey(
        to='users.User', on_delete=models.DO_NOTHING, related_name='user_ratings'
    )
    product = models.ForeignKey(to='scm.Product', on_delete=models.DO_NOTHING, related_name='product_ratings')
    rating = models.PositiveIntegerField(
        db_index=True, default=1, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    description = models.TextField(null=True)
    is_checked = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_product_ratings"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
