
import django_filters

from apps.bases.filters import BaseFilterOrderBy

from .models import (
    FAQ,
    ContactUs,
    FAQCategory,
    FollowUs,
    Language,
    Partner,
    Promotion,
    SupportedBrand,
    TypeOfAddress,
    ValidArea,
    WhoUAre,
    WhoUAreAttachment,
)


class TypeOfAddressFilter(BaseFilterOrderBy):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains"
    )

    class Meta:
        model = TypeOfAddress
        fields = [
            'id',
            'name',
            'is_active'
        ]


class LanguageFilter(BaseFilterOrderBy):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains"
    )

    class Meta:
        model = Language
        fields = [
            'id',
            'name',
        ]


class FAQCategoryFilters(BaseFilterOrderBy):
    """
        FAQCategory filters will be defined here
    """
    name = django_filters.CharFilter(
        field_name='name', lookup_expr='icontains'
    )

    class Meta:
        model = FAQCategory
        fields = [
            'id',
        ]


class FAQFilters(BaseFilterOrderBy):
    """
        FAQ filters will be defined here
    """
    question = django_filters.CharFilter(
        field_name='question', lookup_expr='icontains'
    )
    category = django_filters.CharFilter(
        field_name='category__id', lookup_expr='exact'
    )

    class Meta:
        model = FAQ
        fields = [
            'id',
        ]


class ValidAreaFilters(BaseFilterOrderBy):
    """
        ValidArea filters will be defined here
    """
    name = django_filters.CharFilter(
        field_name='name', lookup_expr='icontains'
    )

    class Meta:
        model = ValidArea
        fields = [
            'id',
            'post_code',
        ]


class SupportedBrandFilters(BaseFilterOrderBy):
    """
        SupportedBrand filters will be defined here
    """
    name = django_filters.CharFilter(
        field_name='name', lookup_expr='icontains'
    )

    class Meta:
        model = SupportedBrand
        fields = [
            'id',
        ]


class PartnerFilters(BaseFilterOrderBy):
    """
        Partner filters will be defined here
    """
    name = django_filters.CharFilter(
        field_name='name', lookup_expr='icontains'
    )

    class Meta:
        model = Partner
        fields = [
            'id',
        ]


class FollowUsFilters(BaseFilterOrderBy):
    """
        FollowUs filters will be defined here
    """
    title = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains'
    )

    class Meta:
        model = FollowUs
        fields = [
            'id',
            'link_type',
        ]


class PromotionFilters(BaseFilterOrderBy):
    """
        Promotion filters will be defined here
    """
    title = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains'
    )

    class Meta:
        model = Promotion
        fields = [
            'id',
        ]


class WhoUAreFilters(BaseFilterOrderBy):
    """
        WhoUAre filters will be defined here
    """
    title = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains'
    )

    class Meta:
        model = WhoUAre
        fields = [
            'id',
            'role',
        ]


class WhoUAreAttachmentFilters(BaseFilterOrderBy):
    """
        WhoUAreAttachment filters will be defined here
    """

    class Meta:
        model = WhoUAreAttachment
        fields = [
            'id',
            'is_cover',
        ]


class ContactUsFilters(BaseFilterOrderBy):
    """
        ContactUs filters will be defined here
    """
    company_name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )
    name = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )
    email = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )
    contact = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )

    class Meta:
        model = ContactUs
        fields = [
            'id',
            'agree_to_privacy_policy',
        ]
