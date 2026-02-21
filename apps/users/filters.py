
import django_filters
from django.db.models import Q

from apps.bases.filters import BaseFilterOrderBy

from ..core.models import ValidArea
from .choices import RoleTypeChoices
from .models import (
    Address,
    ClientDetails,
    Company,
    CompanyBillingAddress,
    Coupon,
    TrackUserLogin,
    UnitOfHistory,
    User,
    UserCoupon,
    Vendor,
    WithdrawRequest,
)


class ClientDetailsFilters(BaseFilterOrderBy):
    """
        Client Filter will define here
    """

    class Meta:
        model = ClientDetails
        fields = [
            'id',
        ]


class UserFilters(BaseFilterOrderBy):
    """
        User Filter will define here
    """
    username = django_filters.CharFilter(
        field_name='username',
        lookup_expr='icontains'
    )
    first_name = django_filters.CharFilter(
        field_name='first_name',
        lookup_expr='icontains'
    )
    last_name = django_filters.CharFilter(
        field_name='last_name',
        lookup_expr='icontains'
    )
    email = django_filters.CharFilter(
        field_name='email',
        lookup_expr='icontains'
    )
    company = django_filters.CharFilter(
        field_name='company__id',
        lookup_expr='exact'
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
    is_blocked = django_filters.BooleanFilter(
        method='is_blocked_filter'
    )
    roles = django_filters.CharFilter(
        method='roles_filter'
    )
    title = django_filters.CharFilter(
        method='title_filter'
    )

    def is_blocked_filter(self, qs, name, value):
        if value:
            qs = qs.filter(
                is_active=False, deactivation_reason=''
            )
        else:
            qs = qs.exclude(
                is_active=False, deactivation_reason=''
            )
        return qs

    def roles_filter(self, qs, name, value):
        qs = qs.filter(
            role__in=value.split(',')
        )
        return qs

    def title_filter(self, qs, name, value):
        qs = qs.filter(
            Q(username__icontains=value) | Q(email__icontains=value) | Q(first_name__icontains=value) | Q(last_name__icontains=value)
        )
        return qs

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'gender',
            'term_and_condition_accepted',
            'privacy_policy_accepted',
            'is_email_verified',
            'is_phone_verified',
            'is_verified',
            'is_active',
            'is_staff',
            'is_superuser',
            'is_deleted',
        ]


class LogsFilters(BaseFilterOrderBy):
    """
        User history Filter will define here
    """
    action = django_filters.CharFilter(
        field_name='action',
        lookup_expr='icontains'
    )
    user = django_filters.CharFilter(
        method='user_filter'
    )
    perform_for = django_filters.CharFilter(
        field_name='perform_for__email',
        lookup_expr='icontains'
    )
    reference_id = django_filters.CharFilter(
        field_name='object_id',
        lookup_expr='icontains'
    )
    content_type = django_filters.CharFilter(
        field_name='content_type__model',
        lookup_expr='icontains'
    )
    created_on = django_filters.CharFilter(
        field_name='created__date', lookup_expr='exact'
    )
    start = django_filters.CharFilter(
        field_name='created__date', lookup_expr='gte'
    )
    end = django_filters.CharFilter(
        field_name='created__date', lookup_expr='lte'
    )

    def user_filter(self, qs, name, value):
        if value:
            qs = qs.filter(
                Q(user__first_name__icontains=value) | Q(user__last_name__icontains=value)
            )
        return qs

    class Meta:
        model = UnitOfHistory
        fields = [
            'id',
            'action',
            'user',
            'perform_for',
            'reference_id',
            'content_type'
        ]


class CompanyFilters(BaseFilterOrderBy):
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )
    email = django_filters.CharFilter(
        field_name='email',
        lookup_expr='icontains'
    )
    working_email = django_filters.CharFilter(
        field_name='working_email',
        lookup_expr='icontains'
    )
    name_email = django_filters.CharFilter(
        method='name_email_filter'
    )
    is_owner_generated = django_filters.BooleanFilter(
        method='is_owner_generated_filter'
    )
    is_valid = django_filters.BooleanFilter(
        method='is_valid_filter'
    )

    def is_owner_generated_filter(self, qs, name, value):
        owner_companies = User.objects.filter(
            role=RoleTypeChoices.COMPANY_OWNER).order_by('company_id').values_list('company_id', flat=True).distinct()
        if value:
            qs = qs.filter(id__in=owner_companies)
        else:
            qs = qs.exclude(id__in=owner_companies)
        return qs

    def is_valid_filter(self, qs, name, value):
        if value:
            qs = qs.filter(post_code__in=ValidArea.objects.filter(
                is_active=True).values_list('post_code', flat=True))
        else:
            qs = qs.exclude(post_code__in=ValidArea.objects.filter(
                is_active=True).values_list('post_code', flat=True))
        return qs

    def name_email_filter(self, qs, name, value):
        return qs.filter(
            Q(name__icontains=value) | Q(email__icontains=value) | Q(working_email__icontains=value) | Q(contact__icontains=value))

    class Meta:
        model = Company
        fields = [
            'id',
            'status',
            'is_checked',
            'is_blocked',
        ]


class VendorFilters(BaseFilterOrderBy):
    """
    """
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )
    email = django_filters.CharFilter(
        field_name='email',
        lookup_expr='icontains'
    )
    title = django_filters.CharFilter(
        method="title_filter",
    )
    has_product = django_filters.BooleanFilter(
        method="has_product_filter",
    )

    def title_filter(self, qs, name, value):
        if value:
            qs = qs.filter(Q(email__icontains=value) | Q(name__icontains=value))
        return qs

    def has_product_filter(self, qs, name, value):
        from apps.scm.models import Product
        vendors = Product.objects.filter(
            vendor__isnull=False, is_deleted=False
        ).order_by('vendor').values_list('vendor_id', flat=True).distinct()
        if value:
            qs = qs.filter(id__in=vendors)
        else:
            qs = qs.exclude(id__in=vendors)
        return qs

    class Meta:
        model = Vendor
        fields = [
            'id',
            'is_blocked',
            'has_product'
        ]


class TrackUserLoginFilters(BaseFilterOrderBy):
    username = django_filters.CharFilter(
        field_name='username',
        lookup_expr='icontains'
    )
    email = django_filters.CharFilter(
        field_name='email',
        lookup_expr='icontains'
    )

    class Meta:
        model = TrackUserLogin
        fields = [
            'id',
        ]


class CouponFilters(BaseFilterOrderBy):
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains'
    )

    class Meta:
        model = Coupon
        fields = [
            'id',
            'is_active',
        ]


class UserCouponFilters(BaseFilterOrderBy):
    coupon = django_filters.CharFilter(
        field_name='coupon__id',
        lookup_expr='icontains'
    )

    class Meta:
        model = UserCoupon
        fields = [
            'id',
        ]


class AddressFilters(BaseFilterOrderBy):

    class Meta:
        model = Address
        fields = [
            'id',
        ]


class CompanyBillingAddressFilters(BaseFilterOrderBy):

    class Meta:
        model = CompanyBillingAddress
        fields = [
            'id',
        ]


class WithdrawRequestFilters(BaseFilterOrderBy):
    """

    """
    vendor = django_filters.CharFilter(
        field_name="vendor__id", lookup_expr="exact"
    )
    vendor_title = django_filters.CharFilter(
        method="vendor_title_filter"
    )

    def vendor_title_filter(self, qs, name, value):
        return qs.filter(Q(vendor__name__icontains=value) | Q(vendor__email__icontains=value))

    class Meta:
        model = WithdrawRequest
        fields = [
            'id',
            'status',
        ]
