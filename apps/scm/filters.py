
import django_filters
from django.db.models import Q

from apps.bases.filters import BaseFilterOrderBy

from .models import (
    Category,
    FavoriteProduct,
    FoodMeeting,
    Ingredient,
    Product,
    ProductAttachment,
    WeeklyVariant,
)


class CategoryFilters(BaseFilterOrderBy):
    """
        Category Filters will define here
    """
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )
    # parent = django_filters.CharFilter(
    #     field_name='parent__id',
    #     lookup_expr='exact'
    # )
    parent = django_filters.CharFilter(
        method='parent_filter'
    )

    def parent_filter(self, qs, name, value):
        if value == '0':
            qs = qs.filter(parent__isnull=True)
        elif value:
            try:
                qs = qs.filter(parent_id=value)
            except Exception:
                qs = qs.filter(id=None)
        return qs

    class Meta:
        model = Category
        fields = [
            'id',
            'is_active',
            'name',
        ]


class WeeklyVariantFilters(BaseFilterOrderBy):
    """
        WeeklyVariant Filters will define here
    """
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )

    class Meta:
        model = WeeklyVariant
        fields = [
            'id',
            'is_active',
            'name',
        ]


class ProductFilters(BaseFilterOrderBy):
    """
        Product filters will be defined here
    """
    title = django_filters.CharFilter(
        method="title_filter",
    )
    category = django_filters.CharFilter(
        method='category_filter',
    )
    weekly_variants = django_filters.CharFilter(
        method='weekly_variants_filter',
    )
    vendor = django_filters.CharFilter(
        field_name='vendor__id', lookup_expr='exact'
    )
    created_on = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='exact'
    )
    updated_on = django_filters.CharFilter(
        field_name='updated_on__date', lookup_expr='exact'
    )
    start = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='gte'
    )
    end = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='lte'
    )
    min_price = django_filters.CharFilter(
        field_name='price', lookup_expr='gte'
    )
    max_price = django_filters.CharFilter(
        field_name='price', lookup_expr='lte'
    )
    is_vendor_product = django_filters.BooleanFilter(
        method="is_vendor_product_filter"
    )

    def category_filter(self, qs, name, value):
        if value == '0':
            qs = qs.filter(category__isnull=True)
        else:
            qs = qs.filter(category__id=value)
        return qs

    def weekly_variants_filter(self, qs, name, value):
        try:
            values = str(value).split(',')
            return qs.filter(weekly_variants__in=WeeklyVariant.objects.filter(id__in=values))
        except Exception:
            return qs.filter(weekly_variants__isnull=True)

    def title_filter(self, qs, name, value):
        if value:
            qs = qs.filter(Q(title__icontains=value) | Q(description__icontains=value) | Q(name__icontains=value))
        return qs

    def is_vendor_product_filter(self, qs, name, value):
        if value:
            qs = qs.filter(vendor__isnull=False)
        else:
            qs = qs.filter(vendor__isnull=True)
        return qs

    class Meta:
        model = Product
        fields = [
            'id',
            'title',
            'availability',
            'is_featured',
            'is_deleted',
        ]


class IngredientFilters(BaseFilterOrderBy):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains"
    )

    class Meta:
        model = Ingredient
        fields = [
            'id',
            'is_active',
            'is_deleted',
        ]


class ProductAttachmentFilters(BaseFilterOrderBy):

    class Meta:
        model = ProductAttachment
        fields = [
            'id',
            'is_cover',
        ]


class FoodMeetingFilters(BaseFilterOrderBy):
    title = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains"
    )
    company_name_email = django_filters.CharFilter(
        method="company_name_email_filter"
    )

    def company_name_email_filter(self, qs, name, value):
        return qs.filter(
            Q(company__name__icontains=value) | Q(company__working_email__icontains=value) | Q(email__icontains=value) | Q(company_name__icontains=value)
        )

    class Meta:
        model = FoodMeeting
        fields = [
            'id',
            'meeting_type',
            'status',
        ]


class FavoriteProductFilters(BaseFilterOrderBy):

    class Meta:
        model = FavoriteProduct
        fields = [
            'id',
        ]
