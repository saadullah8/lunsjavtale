
# third party imports
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

# local imports
from apps.sales.filters import (
    AlterCartFilters,
    BillingAddressFilters,
    OrderFilters,
    OrderPaymentFilters,
    OrderStatusFilters,
    PaymentMethodFilters,
    ProductRatingFilters,
    SellCartFilters,
    UserCartFilters,
)
from backend.count_connection import CountConnection

from ..users.object_types import VendorType
from .models import (
    AlterCart,
    BillingAddress,
    Order,
    OrderPayment,
    OrderStatus,
    PaymentMethod,
    ProductRating,
    SellCart,
    UserCart,
)


class PaymentMethodType(DjangoObjectType):
    """
        define django object type for PaymentMethod model with PaymentMethod filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = PaymentMethod
        filterset_class = PaymentMethodFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class SellCartType(DjangoObjectType):
    """
        define django object type for SellCart model with SellCart filter-set
    """
    id = graphene.ID(required=True)
    ordered_quantity = graphene.Int()
    due_amount = graphene.Decimal()
    vendor = graphene.Field(VendorType)

    class Meta:
        model = SellCart
        filterset_class = SellCartFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_ordered_quantity(self, info, **kwargs):
        return self.ordered_quantity

    def resolve_vendor(self, info, **kwargs):
        return self.item.vendor


class UserCartType(DjangoObjectType):
    """
        define django object type for UserCart model with UserCart filter-set
    """
    id = graphene.ID(required=True)
    is_full_paid = graphene.Boolean()
    due_amount = graphene.Decimal()

    class Meta:
        model = UserCart
        filterset_class = UserCartFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_is_full_paid(self, info, **kwargs):
        return self.is_full_paid


class AlterCartType(DjangoObjectType):
    """
        define django object type for UserCart model with UserCart filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = AlterCart
        filterset_class = AlterCartFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class OrderType(DjangoObjectType):
    """
        define django object type for Order model with Order filter-set
    """
    id = graphene.ID(required=True)
    due_amount = graphene.Decimal()
    company_due_amount = graphene.Decimal()
    employee_due_amount = graphene.Decimal()

    class Meta:
        model = Order
        filterset_class = OrderFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class OrderStatusType(DjangoObjectType):
    """
        define django object type for Order Status model with Order filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = OrderStatus
        filterset_class = OrderStatusFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class BillingAddressType(DjangoObjectType):
    """
        define django object type for Order model with Order filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = BillingAddress
        filterset_class = BillingAddressFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class OrderSummaryType(graphene.ObjectType):
    """
    """
    added_carts = DjangoFilterConnectionField(SellCartType)
    actual_price = graphene.Decimal()
    shipping_charge = graphene.Decimal()
    final_price = graphene.Decimal()


class OrderPaymentType(DjangoObjectType):
    """
        define django object type for OrderPayment model with OrderPayment filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = OrderPayment
        filterset_class = OrderPaymentFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class ProductRatingType(DjangoObjectType):
    """
        define django object type for ProductRating model with ProductRating filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = ProductRating
        filterset_class = ProductRatingFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class AddedCartsListType(graphene.ObjectType):
    date = graphene.Date()
    total_price = graphene.Decimal()
    carts = DjangoFilterConnectionField(SellCartType)
