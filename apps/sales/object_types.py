
from decimal import Decimal

# third party imports
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene.types.generic import GenericScalar

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
    ClientOrder,
    ClientOrderItem,
)
from .choices import InvoiceStatusChoices


CUSTOMER_VISIBLE_STATUSES = [
    InvoiceStatusChoices.CONFIRMED,
    InvoiceStatusChoices.PROCESSING,
    InvoiceStatusChoices.READY_TO_DELIVER,
    InvoiceStatusChoices.DELIVERED,
]

VENDOR_ORDER_ACTIONS = {
    InvoiceStatusChoices.PLACED: ["accept", "reject"],
    InvoiceStatusChoices.UPDATED: ["accept", "reject"],
    InvoiceStatusChoices.CONFIRMED: ["preparing", "request-changes"],
    InvoiceStatusChoices.PROCESSING: ["ready", "out-for-delivery"],
    InvoiceStatusChoices.READY_TO_DELIVER: ["out-for-delivery", "delivered"],
}


def _vendor_carts(order, user):
    qs = order.order_carts.all()
    if user and user.is_vendor:
        qs = qs.filter(item__vendor=user.vendor)
    return qs


def _ordered_quantity(carts):
    return sum(cart.ordered_quantity for cart in carts)


def _customer_details_visible(order, user):
    if not user or not user.is_vendor:
        return True
    return order.status in CUSTOMER_VISIBLE_STATUSES


def _vendor_subtotal(order, user):
    return sum(
        (cart.total_price_with_tax for cart in _vendor_carts(order, user)),
        Decimal("0.00")
    )


def _platform_commission_percent(order, user):
    if user and user.is_vendor:
        return user.vendor.effective_commission_percentage
    first_cart = _vendor_carts(order, user).select_related('item__vendor').first()
    if first_cart and first_cart.item.vendor:
        return first_cart.item.vendor.effective_commission_percentage
    return 0


def _platform_commission_amount(order, user):
    subtotal = _vendor_subtotal(order, user)
    percent = _platform_commission_percent(order, user)
    return subtotal * Decimal(percent) / Decimal("100")


def _money(value):
    return str(value or Decimal("0.00"))


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
    event_name = graphene.String()
    guest_count = graphene.Int()
    delivery_window = GenericScalar()
    customer_details_visible = graphene.Boolean()
    customer_info = GenericScalar()
    order_history = GenericScalar()
    lifecycle_actions = graphene.List(graphene.String)
    vendor_subtotal = graphene.Decimal()
    add_ons_total = graphene.Decimal()
    platform_commission_percent = graphene.Int()
    platform_commission_amount = graphene.Decimal()
    net_earnings = graphene.Decimal()
    special_instructions = graphene.String()

    class Meta:
        model = Order
        filterset_class = OrderFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_order_carts(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _vendor_carts(self, user)

    def resolve_event_name(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        first_cart = _vendor_carts(self, user).select_related('item').first()
        if first_cart and first_cart.item:
            return first_cart.item.title or first_cart.item.name
        return self.note or f"Order #{self.id}"

    def resolve_guest_count(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _ordered_quantity(_vendor_carts(self, user))

    def resolve_delivery_window(self, info, **kwargs):
        return {
            "date": self.delivery_date.isoformat() if self.delivery_date else None,
            "start": None,
            "end": None,
            "label": None,
        }

    def resolve_customer_details_visible(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _customer_details_visible(self, user)

    def resolve_customer_info(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        visible = _customer_details_visible(self, user)
        address = self.shipping_address
        company = self.company
        base = {
            "masked": not visible,
            "organization": company.name,
            "returningCustomerOrders": company.orders.exclude(id=self.id).count(),
        }
        if not visible:
            return base
        base.update({
            "email": company.working_email or company.email,
            "phone": company.contact,
            "postCode": company.post_code,
            "deliveryAddress": address.address if address else None,
            "city": address.city if address else None,
            "state": address.state if address else None,
            "country": address.country if address else None,
            "contactName": address.full_name if address else None,
            "contactPhone": address.phone if address else None,
            "deliveryInstruction": address.instruction if address else None,
        })
        return base

    def resolve_order_history(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        orders = self.company.orders.exclude(id=self.id)
        if user and user.is_vendor:
            orders = orders.filter(order_carts__item__vendor=user.vendor).distinct()
        orders = orders.order_by('-created_on')[:10]
        return [
            {
                "id": order.id,
                "eventName": OrderType.resolve_event_name(order, info),
                "status": order.status,
                "deliveryDate": order.delivery_date.isoformat() if order.delivery_date else None,
                "guestCount": OrderType.resolve_guest_count(order, info),
                "finalPrice": _money(order.final_price),
            }
            for order in orders
        ]

    def resolve_lifecycle_actions(self, info, **kwargs):
        return VENDOR_ORDER_ACTIONS.get(self.status, [])

    def resolve_vendor_subtotal(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _vendor_subtotal(self, user)

    def resolve_add_ons_total(self, info, **kwargs):
        return Decimal("0.00")

    def resolve_platform_commission_percent(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _platform_commission_percent(self, user)

    def resolve_platform_commission_amount(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _platform_commission_amount(self, user)

    def resolve_net_earnings(self, info, **kwargs):
        user = getattr(info.context, 'user', None)
        return _vendor_subtotal(self, user) - _platform_commission_amount(self, user)

    def resolve_special_instructions(self, info, **kwargs):
        return self.note


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
    tags = GenericScalar()
    has_reply = graphene.Boolean()
    order_meta = GenericScalar()

    class Meta:
        model = ProductRating
        filterset_class = ProductRatingFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_has_reply(self, info, **kwargs):
        return bool(self.reply_text)

    def resolve_order_meta(self, info, **kwargs):
        if not self.order:
            return None
        return {
            "id": self.order.id,
            "orderId": f"#ORD-{self.order.id}",
            "amount": str(self.order.final_price or 0),
            "orderType": self.order.payment_type,
            "deliveryDate": self.order.delivery_date.isoformat() if self.order.delivery_date else None,
        }


class AddedCartsListType(graphene.ObjectType):
    date = graphene.Date()
    total_price = graphene.Decimal()
    carts = DjangoFilterConnectionField(SellCartType)

class ClientOrderItemType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = ClientOrderItem
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        filter_fields = ['id']

class ClientOrderType(DjangoObjectType):
    id = graphene.ID(required=True)
    items = graphene.List(ClientOrderItemType)
    due_date = graphene.Date()
    
    class Meta:
        model = ClientOrder
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection
        filter_fields = ['id', 'status']

    def resolve_items(self, info, **kwargs):
        return self.items.all()


class InvoiceSummaryType(graphene.ObjectType):
    total_invoices = graphene.Int()
    paid_invoices = graphene.Int()
    unpaid_invoices = graphene.Int()
    overdue_invoices = graphene.Int()
    
    total_spent = graphene.Decimal()
    this_month_spent = graphene.Decimal()
    pending_amount = graphene.Decimal()
    overdue_amount = graphene.Decimal()


class OrderQuickSummaryType(graphene.ObjectType):
    total_orders = graphene.Int()
    completed = graphene.Int()
    scheduled = graphene.Int()
    drafts = graphene.Int()


class ClientDashboardType(graphene.ObjectType):
    total_orders = graphene.Int()
    pending_invoices = graphene.Int()
    reward_points = graphene.Int()
    recent_orders = graphene.List(ClientOrderType)
    recent_invoices = graphene.List(ClientOrderType)
