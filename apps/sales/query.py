# third party imports
import datetime
from decimal import Decimal

import graphene
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from graphene.types.generic import GenericScalar
from graphene_django.filter.fields import DjangoFilterConnectionField

from apps.scm.models import Product
from apps.scm.object_types import ProductType
from apps.users.choices import RoleTypeChoices
from backend.permissions import is_authenticated, is_company_user

from .models import Order, OrderPayment, PaymentMethod, ProductRating, SellCart
from .choices import InvoiceStatusChoices
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


REVIEW_DATE_RANGES = {
    "last-month": 30,
    "last-3-months": 90,
    "last-6-months": 180,
    "this-year": None,
}


def _money(value):
    return str(value or Decimal("0.00"))


def _review_date_filter(qs, date_range=None, start_date=None, end_date=None):
    if date_range:
        if date_range not in REVIEW_DATE_RANGES:
            raise ValueError("Please select a valid date range.")
        if date_range == "this-year":
            qs = qs.filter(created_on__date__gte=datetime.date(timezone.now().year, 1, 1))
        else:
            qs = qs.filter(created_on__date__gte=timezone.now().date() - datetime.timedelta(days=REVIEW_DATE_RANGES[date_range]))
    if start_date:
        try:
            qs = qs.filter(created_on__date__gte=datetime.date.fromisoformat(start_date))
        except (TypeError, ValueError):
            raise ValueError("Please provide a valid start date.")
    if end_date:
        try:
            qs = qs.filter(created_on__date__lte=datetime.date.fromisoformat(end_date))
        except (TypeError, ValueError):
            raise ValueError("Please provide a valid end date.")
    return qs


def _vendor_reviews(vendor):
    return ProductRating.objects.filter(product__vendor=vendor).select_related(
        "added_by", "product", "order", "order__company"
    )


def _rating_distribution(qs):
    total = qs.count()
    distribution = {}
    for rating in range(5, 0, -1):
        count = qs.filter(rating=rating).count()
        distribution[str(rating)] = {
            "count": count,
            "percent": round((count / total) * 100, 2) if total else 0,
        }
    return distribution


def _review_customer(user):
    return {
        "id": user.id,
        "name": user.full_name or user.email,
        "email": user.email,
        "photoUrl": user.photo_url,
    }


def _review_order_meta(review):
    order = review.order
    if not order:
        return None
    return {
        "id": order.id,
        "orderId": f"#ORD-{order.id}",
        "amount": _money(order.final_price),
        "orderType": order.payment_type,
        "deliveryDate": order.delivery_date.isoformat() if order.delivery_date else None,
        "reviewedOn": review.created_on.isoformat() if review.created_on else None,
    }


def _review_row(review):
    return {
        "id": review.id,
        "customer": _review_customer(review.added_by),
        "product": {
            "id": review.product.id,
            "name": review.product.title or review.product.name,
        },
        "rating": review.rating,
        "description": review.description,
        "tags": review.tags or [],
        "createdOn": review.created_on.isoformat() if review.created_on else None,
        "order": _review_order_meta(review),
        "hasReply": bool(review.reply_text),
        "replyText": review.reply_text,
        "repliedOn": review.replied_on.isoformat() if review.replied_on else None,
        "attentionRequired": review.attention_required,
    }


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
    vendor_review_summary = GenericScalar(
        date_range=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
    )
    vendor_reviews = GenericScalar(
        rating=graphene.Int(),
        date_range=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
        search=graphene.String(),
        first=graphene.Int(),
        offset=graphene.Int(),
    )
    added_carts_list = graphene.List(AddedCartsListType)
    get_online_payment_info = GenericScalar(id=graphene.ID())
    order_summary = GenericScalar(company_allowance=graphene.Int())
    vendor_order_summary = GenericScalar()

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
        elif user.is_vendor:
            qs = qs.filter(order_carts__item__vendor=user.vendor).distinct()
        else:
            qs = qs.filter(company=user.company)
            if user.role == RoleTypeChoices.COMPANY_EMPLOYEE:
                qs = qs.filter(
                    id__in=user.cart_items.filter(cart__order__isnull=False).values_list('cart__order_id', flat=True)
                )
        return qs

    @is_authenticated
    def resolve_vendor_order_summary(self, info, **kwargs):
        user = info.context.user
        if not user.is_vendor:
            return {
                'totalOrders': 0,
                'newOrders': 0,
                'accepted': 0,
                'preparing': 0,
                'ready': 0,
                'outForDelivery': 0,
                'delivered': 0,
            }
        qs = Order.objects.filter(
            is_deleted=False,
            order_carts__item__vendor=user.vendor
        ).distinct()
        return {
            'totalOrders': qs.count(),
            'newOrders': qs.filter(status=InvoiceStatusChoices.PLACED).count(),
            'accepted': qs.filter(status=InvoiceStatusChoices.CONFIRMED).count(),
            'preparing': qs.filter(status=InvoiceStatusChoices.PROCESSING).count(),
            'ready': qs.filter(status=InvoiceStatusChoices.READY_TO_DELIVER).count(),
            'outForDelivery': 0,
            'delivered': qs.filter(status=InvoiceStatusChoices.DELIVERED).count(),
        }

    @is_authenticated
    def resolve_order(self, info, id, **kwargs):
        user = info.context.user
        qs = Order.objects.filter(is_deleted=False)
        if user.is_admin:
            qs = qs.filter(id=id)
            qs.update(is_checked=True)
        elif user.is_vendor:
            qs = qs.filter(id=id, order_carts__item__vendor=user.vendor).distinct()
        else:
            qs = qs.filter(company=user.company, id=id)
            if hasattr(user, 'role') and user.role == 'company-employee':
                qs = qs.filter(
                    id__in=user.cart_items.filter(cart__order__isnull=False).values_list('cart__order_id', flat=True)
                )
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
    def resolve_vendor_review_summary(self, info, date_range=None, start_date=None, end_date=None, **kwargs):
        user = info.context.user
        if not user.is_vendor:
            return {
                "averageRating": 0,
                "totalReviews": 0,
                "newReviews": 0,
                "responseRate": 0,
                "distribution": _rating_distribution(ProductRating.objects.none()),
            }
        try:
            qs = _review_date_filter(_vendor_reviews(user.vendor), date_range, start_date, end_date)
        except ValueError as exc:
            from apps.bases.utils import raise_graphql_error
            raise_graphql_error(str(exc), field_name="dateRange")
        total = qs.count()
        replied = qs.exclude(reply_text__isnull=True).exclude(reply_text="").count()
        new_reviews = qs.filter(is_checked=False).count()
        return {
            "averageRating": round(qs.aggregate(avg=Avg("rating"))["avg"] or 0, 2),
            "totalReviews": total,
            "newReviews": new_reviews,
            "responseRate": round((replied / total) * 100, 2) if total else 0,
            "distribution": _rating_distribution(qs),
        }

    @is_authenticated
    def resolve_vendor_reviews(
        self,
        info,
        rating=None,
        date_range=None,
        start_date=None,
        end_date=None,
        search=None,
        first=10,
        offset=0,
        **kwargs
    ):
        user = info.context.user
        if not user.is_vendor:
            return {"totalCount": 0, "offset": 0, "first": first or 10, "results": []}
        try:
            qs = _review_date_filter(_vendor_reviews(user.vendor), date_range, start_date, end_date)
        except ValueError as exc:
            from apps.bases.utils import raise_graphql_error
            raise_graphql_error(str(exc), field_name="dateRange")
        if rating:
            qs = qs.filter(rating=rating)
        if search and str(search).strip():
            term = str(search).strip()
            qs = qs.filter(
                Q(added_by__first_name__icontains=term) |
                Q(added_by__last_name__icontains=term) |
                Q(added_by__email__icontains=term) |
                Q(product__name__icontains=term) |
                Q(product__title__icontains=term) |
                Q(description__icontains=term)
            )
        total_count = qs.count()
        first = max(1, min(int(first or 10), 100))
        offset = max(0, int(offset or 0))
        return {
            "totalCount": total_count,
            "offset": offset,
            "first": first,
            "results": [_review_row(review) for review in qs.order_by("-created_on", "-id")[offset:offset + first]],
        }

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
