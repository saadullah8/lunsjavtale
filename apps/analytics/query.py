import datetime

import graphene
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
from graphene.types.generic import GenericScalar

from apps.bases.utils import get_serialized_data, raise_graphql_error
from apps.sales.models import Order, ProductRating, SellCart
from apps.scm.models import Product
from apps.users.choices import RoleTypeChoices
from apps.users.models import Company
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
