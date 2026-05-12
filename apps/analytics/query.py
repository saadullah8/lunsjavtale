import datetime
from decimal import Decimal

import graphene
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
from graphene.types.generic import GenericScalar

from apps.bases.utils import get_serialized_data, raise_graphql_error
from apps.sales.choices import InvoiceStatusChoices
from apps.sales.models import Order, ProductRating, SellCart
from apps.scm.models import Product
from apps.users.choices import RoleTypeChoices, WithdrawRequestChoices
from apps.users.models import Company, VendorDeliverySettings
from backend.permissions import is_admin_user, is_vendor_user

User = get_user_model()


class QueryDateRangeChoices(models.TextChoices):
    LAST_7_DAYS = 'last-7-days'
    LAST_30_DAYS = 'last-30-days'
    LAST_6_MONTHS = 'last-6-months'
    LAST_12_MONTHS = 'last-12-months'


DATE_RANGE = {
    QueryDateRangeChoices.LAST_7_DAYS: 7,
    QueryDateRangeChoices.LAST_30_DAYS: 30,
    QueryDateRangeChoices.LAST_6_MONTHS: 6 * 30 + 3,
    QueryDateRangeChoices.LAST_12_MONTHS: 365,
}


PAID_WITHDRAW_STATUSES = [
    WithdrawRequestChoices.ACCEPTED,
    WithdrawRequestChoices.COMPLETED,
]


def _money(value):
    return str(value or Decimal("0.00"))


def _date_window(date_range="", start_date=None, end_date=None):
    if date_range and date_range not in QueryDateRangeChoices:
        raise_graphql_error("Please select a valid choice.", field_name="dateRange")
    if date_range:
        start = timezone.now().date() - datetime.timedelta(days=DATE_RANGE[date_range])
    elif start_date:
        try:
            start = datetime.date.fromisoformat(start_date)
        except (TypeError, ValueError):
            raise_graphql_error("Please provide a valid start date.", field_name="startDate")
    else:
        start = None

    if end_date:
        try:
            end = datetime.date.fromisoformat(end_date)
        except (TypeError, ValueError):
            raise_graphql_error("Please provide a valid end date.", field_name="endDate")
    else:
        end = timezone.now().date()
    return start, end


def _vendor_carts(vendor, start=None, end=None):
    qs = SellCart.objects.filter(
        item__vendor=vendor,
        order__isnull=False,
        order__is_deleted=False,
    ).select_related("order", "order__company", "item")
    if start:
        qs = qs.filter(order__delivery_date__gte=start)
    if end:
        qs = qs.filter(order__delivery_date__lte=end)
    return qs


def _vendor_orders(vendor, start=None, end=None):
    qs = Order.objects.filter(
        is_deleted=False,
        order_carts__item__vendor=vendor,
    ).distinct().select_related("company")
    if start:
        qs = qs.filter(delivery_date__gte=start)
    if end:
        qs = qs.filter(delivery_date__lte=end)
    return qs


def _commission_percent(vendor):
    return Decimal(vendor.effective_commission_percentage or 0)


def _commission_amount(amount, vendor):
    return (amount or Decimal("0.00")) * _commission_percent(vendor) / Decimal("100")


def _chart_range(start, end):
    if not start:
        start = end - datetime.timedelta(days=29)
    return start, end


def _finance_chart(vendor, start, end):
    start, end = _chart_range(start, end)
    chart = []
    day = start
    while day <= end:
        day_carts = _vendor_carts(vendor, day, day)
        earnings = day_carts.aggregate(total=Sum("total_price_with_tax"))["total"] or Decimal("0.00")
        chart.append({
            "date": day.isoformat(),
            "earnings": _money(earnings),
            "orders": _vendor_orders(vendor, day, day).count(),
        })
        day += datetime.timedelta(days=1)
    return chart


def _order_event_name(order, vendor):
    cart = order.order_carts.filter(item__vendor=vendor).select_related("item").first()
    if cart and cart.item:
        return cart.item.title or cart.item.name
    return order.note or f"Order #{order.id}"


def _finance_order_row(order, vendor):
    carts = order.order_carts.filter(item__vendor=vendor)
    total = carts.aggregate(total=Sum("total_price_with_tax"))["total"] or Decimal("0.00")
    commission = _commission_amount(total, vendor)
    return {
        "id": order.id,
        "orderId": f"#{order.id}",
        "customer": order.company.name,
        "event": _order_event_name(order, vendor),
        "date": order.delivery_date.isoformat() if order.delivery_date else None,
        "totalAmount": _money(total),
        "commission": _money(commission),
        "netEarnings": _money(total - commission),
        "status": "paid" if order.status == InvoiceStatusChoices.DELIVERED else "pending",
        "orderStatus": order.status,
    }


def _dashboard_order_row(order, vendor):
    carts = order.order_carts.filter(item__vendor=vendor)
    total = carts.aggregate(total=Sum("total_price_with_tax"))["total"] or Decimal("0.00")
    address = order.shipping_address
    return {
        "id": order.id,
        "orderId": f"#{order.id}",
        "event": _order_event_name(order, vendor),
        "customer": order.company.name,
        "deliveryDate": order.delivery_date.isoformat() if order.delivery_date else None,
        "deliveryLabel": _delivery_label(order.delivery_date),
        "deliveryAddress": address.address if address else None,
        "totalAmount": _money(total),
        "status": order.status,
        "actions": _dashboard_order_actions(order.status),
    }


def _dashboard_order_actions(status):
    if status in [InvoiceStatusChoices.PLACED, InvoiceStatusChoices.CONFIRMED]:
        return ["start-preparing", "view-details"]
    if status == InvoiceStatusChoices.PROCESSING:
        return ["mark-ready", "view-details"]
    if status == InvoiceStatusChoices.READY_TO_DELIVER:
        return ["mark-delivered", "view-details"]
    return ["view-details"]


def _delivery_label(delivery_date):
    if not delivery_date:
        return None
    today = timezone.now().date()
    if delivery_date == today:
        return "Due today"
    if delivery_date == today + datetime.timedelta(days=1):
        return "Due tomorrow"
    if delivery_date < today:
        return "Overdue"
    return delivery_date.isoformat()


def _active_vendor_orders(vendor):
    return _vendor_orders(vendor).exclude(
        status__in=[InvoiceStatusChoices.CANCELLED, InvoiceStatusChoices.DELIVERED]
    )


def _capacity_utilization(vendor):
    settings, _ = VendorDeliverySettings.objects.get_or_create(vendor=vendor)
    max_deliveries = settings.max_deliveries_per_day or 0
    today_orders = _vendor_orders(vendor, timezone.now().date(), timezone.now().date()).count()
    if not max_deliveries:
        return {
            "percent": 0,
            "used": today_orders,
            "capacity": 0,
            "label": "Capacity not configured",
        }
    percent = min(round((today_orders / max_deliveries) * 100), 100)
    return {
        "percent": percent,
        "used": today_orders,
        "capacity": max_deliveries,
        "label": "High" if percent >= 80 else "Normal",
    }


def _vendor_kitchen_status(vendor):
    qs = _vendor_orders(vendor)
    return {
        "preparing": qs.filter(status=InvoiceStatusChoices.PROCESSING).count(),
        "ready": qs.filter(status=InvoiceStatusChoices.READY_TO_DELIVER).count(),
        "outForDelivery": 0,
    }


def _dashboard_reviews(vendor, limit=3):
    reviews = ProductRating.objects.filter(product__vendor=vendor).select_related(
        "added_by", "product", "order"
    ).order_by("-created_on")[:limit]
    return [
        {
            "id": review.id,
            "customer": review.added_by.full_name or review.added_by.email,
            "rating": review.rating,
            "description": review.description,
            "createdOn": review.created_on.isoformat() if review.created_on else None,
            "product": review.product.title or review.product.name,
            "orderId": f"#ORD-{review.order_id}" if review.order_id else None,
        }
        for review in reviews
    ]


def _home_earnings_chart(vendor):
    end = timezone.now().date()
    start = end - datetime.timedelta(days=6)
    return _finance_chart(vendor, start, end)


class AdminDashboard:

    def __init__(self, date_range=""):
        if date_range and date_range not in QueryDateRangeChoices:
            raise_graphql_error("Please select a valid choice.", field_name="dateRange")
        self.date_range = date_range

    def get_data(self):
        context = {
            'totalCustomers': Company.objects.count(),
            'totalOrders': Order.objects.count(),
            'totalSales': str(Order.objects.aggregate(tot=Sum('final_price'))['tot'] or '0.00'),
            'totalDue': str(
                (Order.objects.aggregate(tot=Sum('final_price'))['tot'] or 0) - (Order.objects.aggregate(
                    paid=Sum('paid_amount'))['paid'] or 0)
            ),
            'salesToday': str(Order.objects.filter(
                created_on__date=timezone.now().date()
            ).aggregate(tot=Sum('final_price'))['tot'] or '0.00'),
            'recentCustomers': self.get_recent_customers(),
            'recentOrders': self.get_recent_orders(),
            'users': self.get_users(),
            'recentReviews': self.get_recent_ratings(),
            'soldProducts': self.get_sold_products(),
        }
        return context

    def get_recent_customers(self):
        return get_serialized_data(
            Company.objects.order_by('-created_on')[:4], fields=['name', 'email', 'contact', 'logo_url']
        )

    def get_recent_orders(self):
        return get_serialized_data(
            Order.objects.order_by('-created_on')[:4], fields=[
                'company__name', 'final_price', 'delivery_date', 'created_on', 'status'
            ]
        )

    def get_users(self):
        return get_serialized_data(
            User.objects.filter(
                role__in=[
                    RoleTypeChoices.ADMIN, RoleTypeChoices.DEVELOPER, RoleTypeChoices.SUB_ADMIN, RoleTypeChoices.EDITOR,
                    RoleTypeChoices.SEO_MANAGER, RoleTypeChoices.SYSTEM_MANAGER
                ]
            )[:4], fields=['first_name', 'last_name', 'email', 'photo_url', 'role']
        )

    def get_recent_ratings(self):
        return get_serialized_data(
            ProductRating.objects.order_by('-created_on')[:4],
            fields=['added_by__first_name', 'added_by__last_name', 'product__name', 'rating', 'description']
        )

    def get_sold_products(self):
        if self.date_range:
            date = timezone.now().date() - datetime.timedelta(days=DATE_RANGE[self.date_range])
            carts = SellCart.objects.filter(date__gte=date, order__isnull=False)
        else:
            carts = SellCart.objects.filter(order__isnull=False)
        products = list(carts.filter(item__is_deleted=False).order_by('item').values_list('item_id', flat=True).distinct())
        sold_products = []
        for product_id in products:
            product = Product.objects.filter(id=product_id).last()
            if product:
                sold_products.append({
                    'id': product_id,
                    'name': product.name,
                    'soldAmount': carts.filter(item=product).aggregate(tot=Sum('total_price_with_tax'))['tot']
                })
        sold_products = sorted(sold_products, key=lambda d: d['soldAmount'], reverse=True)[:5]
        return list(map(lambda i: {
            'id': i['id'],
            'name': i['name'],
            'soldAmount': str(i['soldAmount'])
        }, sold_products))

    def get_sales_history(self):
        pass


class VendorDashboard:

    def __init__(self, vendor, date_range=""):
        if date_range and date_range not in QueryDateRangeChoices:
            raise_graphql_error("Please select a valid choice.", field_name="dateRange")
        self.date_range = date_range
        self.vendor = vendor

    def get_data(self):
        context = {
            'totalOrders': SellCart.objects.filter(
                item__vendor=self.vendor
            ).order_by('order').values_list('order', flat=True).distinct().count(),
            'totalSales': str(SellCart.objects.filter(
                item__vendor=self.vendor).aggregate(tot=Sum('total_price_with_tax'))['tot'] or '0.00'),
            'salesToday': str(SellCart.objects.filter(
                created_on__date=timezone.now().date(), item__vendor=self.vendor
            ).aggregate(tot=Sum('total_price_with_tax'))['tot'] or '0.00'),
            'recentSales': self.get_recent_orders(),
            'recentReviews': self.get_recent_ratings(),
            'soldProducts': self.get_sold_products(),
        }
        return context

    def get_sold_products(self):
        if self.date_range:
            date = timezone.now().date() - datetime.timedelta(days=DATE_RANGE[self.date_range])
            carts = SellCart.objects.filter(date__gte=date, order__isnull=False, item__vendor=self.vendor)
        else:
            carts = SellCart.objects.filter(order__isnull=False, item__vendor=self.vendor)
        products = list(carts.filter(item__is_deleted=False).order_by('item').values_list('item_id', flat=True).distinct())
        sold_products = []
        for product_id in products:
            product = Product.objects.filter(id=product_id).last()
            if product:
                sold_products.append({
                    'id': product_id,
                    'name': product.name,
                    'soldAmount': carts.filter(item=product).aggregate(tot=Sum('total_price_with_tax'))['tot']
                })
        sold_products = sorted(sold_products, key=lambda d: d['soldAmount'], reverse=True)[:5]
        return list(map(lambda i: {
            'id': i['id'],
            'name': i['name'],
            'soldAmount': str(i['soldAmount'])
        }, sold_products))

    def get_recent_orders(self):
        return get_serialized_data(
            SellCart.objects.filter(item__vendor=self.vendor).order_by('-created_on')[:4], fields=[
                'order__company__name', 'total_price_with_tax', 'date'
            ]
        )

    def get_recent_ratings(self):
        return get_serialized_data(
            ProductRating.objects.filter(product__vendor=self.vendor).order_by('-created_on')[:4],
            fields=['added_by__first_name', 'added_by__last_name', 'product__name', 'rating', 'description']
        )


class AnalyticsType(graphene.ObjectType):
    data = GenericScalar()


class Query(graphene.ObjectType):
    """
        define all queries together
    """
    admin_dashboard = graphene.Field(
        AnalyticsType, date_range=graphene.String()
    )
    vendor_dashboard = graphene.Field(
        AnalyticsType, date_range=graphene.String()
    )
    company_due = GenericScalar(date_range=graphene.String())
    vendor_finance_summary = GenericScalar(
        date_range=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
    )
    vendor_finance_orders = GenericScalar(
        date_range=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
        search=graphene.String(),
        first=graphene.Int(),
        offset=graphene.Int(),
    )
    vendor_home_dashboard = GenericScalar()

    @is_admin_user
    def resolve_admin_dashboard(self, info, date_range="", **kwargs):
        data = AdminDashboard(date_range).get_data()
        return AnalyticsType(
            data=data
        )

    @is_vendor_user
    def resolve_vendor_dashboard(self, info, date_range="", **kwargs):
        vendor = info.context.user.vendor
        data = VendorDashboard(vendor, date_range).get_data()
        return AnalyticsType(
            data=data
        )

    @is_vendor_user
    def resolve_vendor_finance_summary(self, info, date_range="", start_date=None, end_date=None, **kwargs):
        vendor = info.context.user.vendor
        start, end = _date_window(date_range, start_date, end_date)
        carts = _vendor_carts(vendor, start, end)
        orders = _vendor_orders(vendor, start, end)
        total_earnings = carts.aggregate(total=Sum("total_price_with_tax"))["total"] or Decimal("0.00")
        platform_commission = _commission_amount(total_earnings, vendor)
        pending_payouts = vendor.withdraw_requests.filter(
            status=WithdrawRequestChoices.PENDING,
            is_deleted=False,
        ).aggregate(total=Sum("withdraw_amount"))["total"] or Decimal("0.00")
        paid_withdraws = vendor.withdraw_requests.filter(
            status__in=PAID_WITHDRAW_STATUSES,
            is_deleted=False,
        )
        paid_amount = paid_withdraws.aggregate(total=Sum("withdraw_amount"))["total"] or Decimal("0.00")
        last_payout = paid_withdraws.order_by("-updated_on").first()
        return {
            "cards": {
                "totalEarnings": _money(total_earnings),
                "netIncome": _money(total_earnings - platform_commission),
                "platformCommission": _money(platform_commission),
                "pendingPayouts": _money(pending_payouts),
            },
            "payoutStatus": {
                "pendingAmount": _money(pending_payouts),
                "paidAmount": _money(paid_amount),
                "lastPayoutDate": last_payout.updated_on.date().isoformat() if last_payout else None,
                "availableBalance": _money(vendor.balance),
            },
            "chart": _finance_chart(vendor, start, end),
            "orderCount": orders.count(),
            "dateRange": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
        }

    @is_vendor_user
    def resolve_vendor_finance_orders(
        self,
        info,
        date_range="",
        start_date=None,
        end_date=None,
        search=None,
        first=20,
        offset=0,
        **kwargs
    ):
        vendor = info.context.user.vendor
        start, end = _date_window(date_range, start_date, end_date)
        qs = _vendor_orders(vendor, start, end)
        if search and str(search).strip():
            term = str(search).strip()
            qs = qs.filter(
                models.Q(company__name__icontains=term) |
                models.Q(company__working_email__icontains=term) |
                models.Q(order_carts__item__name__icontains=term) |
                models.Q(order_carts__item__title__icontains=term)
            ).distinct()
            if term.isdigit():
                qs = qs | _vendor_orders(vendor, start, end).filter(id=int(term))
        total_count = qs.count()
        first = max(1, min(int(first or 20), 100))
        offset = max(0, int(offset or 0))
        rows = [_finance_order_row(order, vendor) for order in qs.order_by("-delivery_date", "-id")[offset:offset + first]]
        return {
            "totalCount": total_count,
            "offset": offset,
            "first": first,
            "results": rows,
        }

    @is_vendor_user
    def resolve_vendor_home_dashboard(self, info, **kwargs):
        vendor = info.context.user.vendor
        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)
        all_orders = _vendor_orders(vendor)
        active_orders = _active_vendor_orders(vendor)
        today_orders = _vendor_orders(vendor, today, today)
        yesterday_orders = _vendor_orders(vendor, yesterday, yesterday)
        urgent_orders = active_orders.filter(delivery_date__lte=today).order_by("delivery_date", "id")[:3]
        upcoming_orders = active_orders.filter(delivery_date=today).count()
        return {
            "kitchen": {
                "isActive": vendor.is_kitchen_active,
            },
            "cards": {
                "totalOrders": {
                    "value": all_orders.count(),
                    "comparison": today_orders.count() - yesterday_orders.count(),
                    "label": "vs yesterday",
                },
                "upcomingNext4Hours": {
                    "value": upcoming_orders,
                    "label": "Date-based until delivery time slots are stored on orders",
                },
                "urgentOrders": {
                    "value": active_orders.filter(delivery_date__lte=today).count(),
                    "label": "Require attention",
                },
                "capacityUtilization": _capacity_utilization(vendor),
            },
            "urgentOrders": [_dashboard_order_row(order, vendor) for order in urgent_orders],
            "quickActions": [
                {"key": "add-menu-item", "label": "Add new menu items"},
                {"key": "pending-orders", "label": "View Pending Orders"},
                {"key": "update-availability", "label": "Update Availability"},
            ],
            "kitchenStatus": _vendor_kitchen_status(vendor),
            "earningsOverview": {
                "dateRange": "last-7-days",
                "chart": _home_earnings_chart(vendor),
            },
            "reviews": {
                "latest": _dashboard_reviews(vendor),
                "summary": {
                    "total": ProductRating.objects.filter(product__vendor=vendor).count(),
                    "new": ProductRating.objects.filter(product__vendor=vendor, is_checked=False).count(),
                },
            },
        }

    @is_admin_user
    def resolve_company_due(self, info, date_range="", **kwargs):
        if date_range:
            date = timezone.now().date() - datetime.timedelta(days=DATE_RANGE[self.date_range])
            orders = Order.objects.filter(delivery_date__gte=date)
        else:
            orders = Order.objects.all()
        data = {}
        for order in orders.annotate(due=F('final_price') - F('paid_amount')).filter(due__gt=0):
            try:
                data[order.company.id]['due'] += order.due
            except Exception:
                data[order.company.id] = {
                    'company': {'id': order.company.id, 'workingEmail': order.company.working_email,
                                'name': order.company.name}, 'due': order.due}
        return list(map(lambda k: {'company': k['company'], 'due': str(k['due'])}, list(data.values())))
