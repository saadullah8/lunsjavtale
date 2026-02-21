# third party imports

import graphene
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from graphene.types.generic import GenericScalar
from graphene_django.filter.fields import DjangoFilterConnectionField

from apps.scm.models import Product
from apps.scm.object_types import ProductType
from apps.users.choices import RoleTypeChoices
from backend.permissions import is_authenticated, is_company_user

from .models import Order, OrderPayment, PaymentMethod, ProductRating, SellCart
from .object_types import (
    AddedCartsListType,
    OrderPaymentType,
    OrderType,
    PaymentMethodType,
    ProductRatingType,
    SellCartType,
)
from .tasks import get_payment_info

# local imports

User = get_user_model()


class Query(graphene.ObjectType):
    """
        query all table information.
    """
    payment_methods = DjangoFilterConnectionField(PaymentMethodType)
    payment_method = graphene.Field(PaymentMethodType, id=graphene.ID())
    added_carts = DjangoFilterConnectionField(SellCartType)
    sales_histories = DjangoFilterConnectionField(SellCartType)
    added_products = DjangoFilterConnectionField(ProductType)
    added_employee_carts = DjangoFilterConnectionField(SellCartType)
    cart = graphene.Field(SellCartType, id=graphene.ID())
    orders = DjangoFilterConnectionField(OrderType)
    order = graphene.Field(OrderType, id=graphene.ID())
    order_payments = DjangoFilterConnectionField(OrderPaymentType)
    order_payment = graphene.Field(OrderPaymentType, id=graphene.ID())
    product_ratings = DjangoFilterConnectionField(ProductRatingType)
    product_rating = graphene.Field(ProductRatingType, id=graphene.ID())
    added_carts_list = graphene.List(AddedCartsListType)
    get_online_payment_info = GenericScalar(id=graphene.ID())
    order_summary = GenericScalar(company_allowance=graphene.Int())

    @is_company_user
    def resolve_order_summary(self, info, company_allowance, **kwargs):
        user = info.context.user
        added_carts = SellCart.objects.filter(added_by=user, is_requested=False)
        qty = added_carts.aggregate(t=Sum('quantity'))['t'] or 0
        total_price = 0
        sub_total_price = added_carts.aggregate(t=Sum('total_price'))['t'] or 0
        total_price_with_tax = added_carts.aggregate(t=Sum('total_price_with_tax'))['t'] or 0
        for cart in added_carts:
            total_price += cart.total_price_with_tax - (cart.price_with_tax * (100 - company_allowance) / 100 * cart.added_for.count())
        return {
            'quantity': qty,
            'subTotal': str(sub_total_price),
            'companyAllowance': company_allowance,
            'companyDue': str(total_price),
            'employeeDue': str(total_price_with_tax - total_price),
            'total': str(total_price_with_tax)
        }

    def resolve_get_online_payment_info(self, info, id, **kwargs):
        online_payment = get_payment_info(id)
        return online_payment.session_data if online_payment else False

    @is_authenticated
    def resolve_payment_methods(self, info, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = PaymentMethod.objects.all()
        else:
            qs = PaymentMethod.objects.filter(user=user)
        return qs

    @is_authenticated
    def resolve_payment_method(self, info, id, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = PaymentMethod.objects.filter(id=id)
        else:
            qs = PaymentMethod.objects.filter(user=user, id=id)
        return qs.last()

    @is_authenticated
    def resolve_orders(self, info, **kwargs):
        user = info.context.user
        qs = Order.objects.filter(is_deleted=False)
        if user.is_admin:
            qs = qs
        else:
            qs = qs.filter(company=user.company)
            if user.role == RoleTypeChoices.COMPANY_EMPLOYEE:
                qs = qs.filter(
                    id__in=user.cart_items.filter(cart__order__isnull=False).values_list('cart__order_id', flat=True)
                )
        return qs

    @is_authenticated
    def resolve_order(self, info, id, **kwargs):
        user = info.context.user
        qs = Order.objects.filter(is_deleted=False)
        if user.is_admin:
            qs = qs.filter(id=id)
            qs.update(is_checked=True)
        else:
            qs = qs.filter(company=user.company, id=id)
        return qs.last()

    @is_authenticated
    def resolve_order_payments(self, info, **kwargs):
        user = info.context.user
        qs = OrderPayment.objects.order_by('-created_on')
        if user.is_admin:
            qs = qs
        elif user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            qs = qs.filter(Q(company=user.company) | Q(payment_for=user))
        else:
            qs = qs.filter(payment_for=user)
        return qs

    @is_authenticated
    def resolve_order_payment(self, info, id, **kwargs):
        user = info.context.user
        qs = OrderPayment.objects.all()
        if user.is_admin:
            qs = qs.filter(id=id)
            qs.update(is_checked=True)
        elif user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            qs = qs.filter(Q(order__company=user.company) | Q(user_cart__added_for=user), id=id)
        else:
            qs = qs.filter(user_cart__added_for=user, id=id)
        return qs.last()

    @is_authenticated
    def resolve_product_ratings(self, info, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = ProductRating.objects.all()
        else:
            qs = ProductRating.objects.filter(added_by=user)
        return qs

    @is_authenticated
    def resolve_product_rating(self, info, id, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = ProductRating.objects.filter(id=id)
            qs.update(is_checked=True)
        else:
            qs = ProductRating.objects.filter(added_by=user, id=id)
        return qs.last()

    @is_authenticated
    def resolve_added_carts(self, info, **kwargs):
        user = info.context.user
        qs = SellCart.objects.filter(added_by=user, is_requested=False)
        return qs

    @is_authenticated
    def resolve_sales_histories(self, info, **kwargs):
        user = info.context.user
        qs = SellCart.objects.filter(item__vendor__isnull=False, order__isnull=False, order__is_deleted=False)
        if user.is_admin:
            pass
        elif user.is_vendor:
            qs = qs.filter(item__vendor=user.vendor)
        else:
            qs = qs.filter(id=None)
        return qs

    @is_authenticated
    def resolve_added_carts_list(self, info, **kwargs):
        user = info.context.user
        qs = SellCart.objects.filter(added_by=user, is_requested=False)
        dates = qs.order_by('date').values_list('date', flat=True).distinct()
        new_qs = []
        for date in dates:
            new_qs.append(
                AddedCartsListType(
                    date=date,
                    total_price=qs.filter(date=date).aggregate(t=Sum('total_price_with_tax'))['t'],
                    carts=qs.filter(date=date)
                )
            )
        return new_qs

    @is_authenticated
    def resolve_added_products(self, info, **kwargs):
        user = info.context.user
        qs = SellCart.objects.filter(added_by=user, is_requested=False).order_by('item_id').values_list('item_id', flat=True).distinct()
        return Product.objects.filter(id__in=qs)

    @is_authenticated
    def resolve_added_employee_carts(self, info, **kwargs):
        user = info.context.user
        if user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            qs = SellCart.objects.filter(
                added_by__role=RoleTypeChoices.COMPANY_EMPLOYEE, added_by__company=user.company, is_requested=True
            )
        else:
            qs = SellCart.objects.filter(added_by=user, is_requested=True)
        return qs

    @is_authenticated
    def resolve_cart(self, info, id, **kwargs):
        qs = SellCart.objects.filter(id=id)
        return qs.last()
