# at backend/users/schema.py

import graphene
from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

# local imports
from backend.count_connection import CountConnection

from ..bases.constant import HistoryActions
from .filters import (
    AddressFilters,
    ClientDetailsFilters,
    CompanyBillingAddressFilters,
    CompanyFilters,
    CouponFilters,
    LogsFilters,
    TrackUserLoginFilters,
    UserCouponFilters,
    UserFilters,
    VendorFilters,
    WithdrawRequestFilters,
)
from apps.core.object_types import ValidAreaType
from .models import (
    Address,
    Agreement,
    ClientDetails,
    Company,
    CompanyBillingAddress,
    Coupon,
    TrackUserLogin,
    UnitOfHistory,
    UserCoupon,
    UserDeviceToken,
    Vendor,
    VendorDeliverySettings,
    VendorSettings,
    WithdrawRequest,
    RewardTransaction,
)

User = get_user_model()  # variable taken for User model


class ClientDetailsType(DjangoObjectType):
    """
        Define django object type for Client-details model with filter-set and relay node information
    """
    id = graphene.ID(required=True)

    class Meta:
        model = ClientDetails
        filterset_class = ClientDetailsFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class UserType(DjangoObjectType):
    """
        Define django object type for user model with filter-set and relay node information
    """
    id = graphene.ID(required=True)
    is_admin = graphene.Boolean()
    due_amount = graphene.Decimal()
    added_by = GenericScalar()
    reward_points = graphene.Int()
    rewards_enabled = graphene.Boolean()

    class Meta:
        model = User
        exclude = (
            'performer', 'perform_for'
        )
        filterset_class = UserFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_due_amount(self, info, **kwargs):
        carts = self.cart_items.annotate(due=F('cart__price_with_tax') * (100 - F('cart__order__company_allowance')) / 100 - F('paid_amount'))
        try:
            return round(carts.aggregate(total_due=Sum('due'))['total_due'], 2)
        except Exception:
            return "0.00"

    @staticmethod
    def resolve_added_by(self, info):
        added_by = UnitOfHistory.objects.filter(action=HistoryActions.USER_CREATE, perform_for=self).last()
        return {
            'id': added_by.user.id, 'email': added_by.user.email, 'fullName': added_by.user.full_name,
            'username': added_by.user.username
        } if added_by and added_by.user else None


class RewardTransactionType(DjangoObjectType):
    class Meta:
        model = RewardTransaction
        interfaces = (graphene.relay.Node,)
        connection_class = CountConnection


class LogType(DjangoObjectType):
    """
        Define django object type for user history model with filter-set and relay node information
    """
    id = graphene.ID(required=True)

    class Meta:
        model = UnitOfHistory
        filterset_class = LogsFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class CompanyType(DjangoObjectType):
    """
        Define django object type for user Company model with filter-set and relay node information
    """
    id = graphene.ID(required=True)
    balance = graphene.Decimal()
    total_employee = graphene.Int()
    is_owner_generated = graphene.Boolean()
    is_valid = graphene.Boolean()
    owner = graphene.Field(UserType)

    class Meta:
        model = Company
        filterset_class = CompanyFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_balance(self, info, **kwargs):
        return self.balance

    @staticmethod
    def resolve_total_employee(self, info, **kwargs):
        return self.total_employee

    @staticmethod
    def resolve_owner(self, info, **kwargs):
        return self.owner


class VendorType(DjangoObjectType):
    """
        Define django object type for user Vendor model with filter-set and relay node information
    """
    id = graphene.ID(required=True)
    balance = graphene.Decimal()
    owner = graphene.Field(UserType)
    service_areas = graphene.List(ValidAreaType)
    effective_commission_percentage = graphene.Int()
    delivery_settings = graphene.Field(lambda: VendorDeliverySettingsType)
    business_settings = graphene.Field(lambda: VendorSettingsType)
    company_name = graphene.String()

    class Meta:
        model = Vendor
        filterset_class = VendorFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_balance(self, info, **kwargs):
        return self.balance

    @staticmethod
    def resolve_owner(self, info, **kwargs):
        return self.owner

    @staticmethod
    def resolve_service_areas(self, info, **kwargs):
        return self.service_areas.filter(is_active=True).order_by('name', 'post_code')

    @staticmethod
    def resolve_effective_commission_percentage(self, info, **kwargs):
        return self.effective_commission_percentage

    @staticmethod
    def resolve_delivery_settings(self, info, **kwargs):
        settings, _ = VendorDeliverySettings.objects.get_or_create(vendor=self)
        return settings

    @staticmethod
    def resolve_business_settings(self, info, **kwargs):
        settings, _ = VendorSettings.objects.get_or_create(vendor=self)
        return settings

    def resolve_company_name(self, info):
        return self.name


class VendorDeliverySettingsType(DjangoObjectType):
    id = graphene.ID(required=True)
    delivery_days = GenericScalar()
    delivery_time_slots = GenericScalar()
    live_validation = GenericScalar()

    class Meta:
        model = VendorDeliverySettings
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_live_validation(self, info, **kwargs):
        return self.live_validation


class VendorSettingsType(DjangoObjectType):
    id = graphene.ID(required=True)
    business_hours = GenericScalar()
    notification_preferences = GenericScalar()

    class Meta:
        model = VendorSettings
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class UserDeviceTokenType(DjangoObjectType):
    """
        Define django object type for User Device Token model
    """
    id = graphene.ID(required=True)

    class Meta:
        model = UserDeviceToken


class TrackUserLoginType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = TrackUserLogin
        filterset_class = TrackUserLoginFilters
        interfaces = (graphene.relay.Node, )
        connection_class = CountConnection


class CouponType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = Coupon
        filterset_class = CouponFilters
        interfaces = (graphene.relay.Node, )
        connection_class = CountConnection


class UserCouponType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = UserCoupon
        filterset_class = UserCouponFilters
        interfaces = (graphene.relay.Node, )
        connection_class = CountConnection


class AgreementType(DjangoObjectType):
    """
        Define django object type for user skill model with filter-set and relay node information.
        typeOf choices::
        1. terms-and-conditions
        2. privacy-policy
    """
    id = graphene.ID(required=True)

    class Meta:
        model = Agreement
        filter_fields = {
            'type_of': ['exact', ]
        }
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class AddressType(DjangoObjectType):
    """
    """
    id = graphene.ID(required=True)

    class Meta:
        model = Address
        filterset_class = AddressFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class CompanyBillingAddressType(DjangoObjectType):
    """
    """
    id = graphene.ID(required=True)

    class Meta:
        model = CompanyBillingAddress
        filterset_class = CompanyBillingAddressFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class WithdrawRequestType(DjangoObjectType):
    """
    """
    id = graphene.ID(required=True)

    class Meta:
        model = WithdrawRequest
        filterset_class = WithdrawRequestFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class AppliedCouponType(graphene.ObjectType):
    actual_price = graphene.Float()
    amount_discounted = graphene.Float()
    discounted_price = graphene.Float()
    discounted_value = graphene.String()
