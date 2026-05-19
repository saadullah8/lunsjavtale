# at backend/users/schema.py

import graphene
from graphene.types.generic import GenericScalar
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from graphene_django.forms.mutation import DjangoFormMutation, DjangoModelFormMutation
from graphql import GraphQLError

# local imports
from apps.bases.constant import HistoryActions, VerifyActionChoices
from apps.core.models import ValidArea
from apps.bases.utils import (
    camel_case_format,
    create_token,
    generate_pin,
    get_object_by_attrs,
    get_object_by_id,
    get_object_dict,
    raise_graphql_error,
    raise_graphql_error_with_fields,
    set_absolute_uri,
)
from apps.scm.models import Ingredient
from backend.authentication import TokenManager
from backend.permissions import (
    is_admin_user,
    is_authenticated,
    is_company_user,
    is_super_admin,
)

from ..notifications.tasks import notify_company_registration
from .choices import RoleTypeChoices, WithdrawRequestChoices
from .forms import (
    AddressForm,
    AdminRegistrationForm,
    AgreementForm,
    CompanyBillingAddressForm,
    CompanyForm,
    CompanyUpdateForm,
    CouponForm,
    UserAccountForm,
    UserCreationForm,
    UserForm,
    UserRegisterForm,
    UserRegistrationForm,
    SignupForm,
    ValidCompanyForm,
    VendorForm,
    VendorSignupForm,
    VendorUpdateForm,
)
from .login_backends import signup, social_signup
from .models import (
    AccessToken,
    Address,
    Agreement,
    ClientDetails,
    Company,
    CompanyBillingAddress,
    Coupon,
    ResetPassword,
    UnitOfHistory,
    UserDeviceToken,
    Vendor,
    VendorDeliverySettings,
    VendorSettings,
    WithdrawRequest,
)
from .object_types import (
    AddressType,
    AgreementType,
    AppliedCouponType,
    CompanyBillingAddressType,
    CompanyType,
    CouponType,
    UserType,
    VendorType,
    VendorDeliverySettingsType,
    VendorSettingsType,
)
from .tasks import send_email_on_delay

User = get_user_model()  # variable taken for User model


class SignupFormInput(graphene.InputObjectType):
    email = graphene.String(required=True)
    phone = graphene.String(required=True)
    password = graphene.String(required=True)
    role = graphene.String(required=True)
    first_name = graphene.String()
    last_name = graphene.String()
    company_name = graphene.String()
    post_code = graphene.Int()


class CompanyMutationForAdmin(DjangoModelFormMutation):
    """
        admin can create and update Company information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(CompanyType)

    class Meta:
        form_class = CompanyUpdateForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        logged_user = info.context.user
        if logged_user.is_admin or (
                logged_user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER] and logged_user.company.id == int(input.get('id'))):
            pass
        else:
            raise_graphql_error("Not allowed for this operation.")
        form = CompanyUpdateForm(data=input)
        error_data = {}
        if input.get('id'):
            form = CompanyUpdateForm(data=input, instance=Company.objects.get(id=input.get('id')))
            if form.is_valid():
                obj = form.save()
                owner = obj.owner
                if input.get('first_name'):
                    owner.first_name = input.get('first_name')
                if input.get('contact'):
                    owner.phone = input.get('contact')
                if input.get('address'):
                    owner.address = input.get('address')
                owner.save()
            else:
                for error in form.errors:
                    for err in form.errors[error]:
                        error_data[camel_case_format(error)] = err
                raise_graphql_error_with_fields("Invalid input request.", error_data)
        else:
            user_input = {
                'email': input.get('working_email'),
                'phone': input.get('contact'),
                'role': RoleTypeChoices.COMPANY_OWNER,
                'first_name': input.get('first_name'),
                'address': input.get('address'),
                'post_code': input.get('post_code')
            }
            user_form = UserRegistrationForm(data=user_input)

            if form.is_valid() and user_form.is_valid():
                obj = form.save()
                user = User.objects.create_user(**user_input)
                user.company = obj
                user.save()
                user.send_email_verified()
            else:
                for error in form.errors:
                    for err in form.errors[error]:
                        error_data[camel_case_format(error)] = err
                for error in user_form.errors:
                    for err in user_form.errors[error]:
                        if error == 'phone':
                            error_data['contact'] = err
                        else:
                            error_data[camel_case_format(error)] = err
                raise_graphql_error_with_fields("Invalid input request.", error_data)
        return CompanyMutationForAdmin(
            success=True, message="Successfully added", instance=obj
        )


class CompanyMutation(DjangoFormMutation):
    """
        Users can create Company information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(CompanyType)

    class Meta:
        form_class = CompanyForm

    def mutate_and_get_payload(self, info, **input):
        form = CompanyForm(data=input)
        if form.is_valid():
            obj = form.save()
            notify_company_registration.delay(obj.id)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return CompanyMutation(
            success=True, message="Successfully added", instance=obj
        )


def _perform_user_registration(info, user_input, role, profile_form=None, profile_input=None):
    """
    Helper to handle user creation and profile linking (Vendor/Company).
    """
    error_data = {}
    try:
        validate_password(user_input.get('password'))
    except Exception as e:
        error_data['password'] = list(e)

    # Use existing UserRegisterForm for validation logic reuse
    user_form = UserRegisterForm(data=user_input)
    
    # Profile validation if provided
    profile_obj = None
    if profile_form and profile_input:
        profile_instance_form = profile_form(data=profile_input)
        if not profile_instance_form.is_valid():
            for error in profile_instance_form.errors:
                for err in profile_instance_form.errors[error]:
                    error_data[camel_case_format(error)] = err
        else:
            profile_obj = profile_instance_form

    if user_form.is_valid() and not error_data:
        user = User.objects.create_user(**user_input)
        if profile_obj:
            p_obj = profile_obj.save()
            if role == RoleTypeChoices.VENDOR:
                user.vendor = p_obj
                user.save()
                user.email_verification(user_input.get('password'))
            elif role == RoleTypeChoices.COMPANY_OWNER:
                user.company = p_obj
                user.save()
                user.send_email_verification()
        else:
            if role == RoleTypeChoices.USER:
                user.is_verified = True
                user.is_email_verified = True
                user.save()
        return user, None
    else:
        for error in user_form.errors:
            for err in user_form.errors[error]:
                if error == 'phone':
                    error_data['contact'] = err
                else:
                    error_data[camel_case_format(error)] = err
        return None, error_data


class ValidCompanyMutation(DjangoFormMutation):
    """
        Users can create valid Company information through a form input.\n
        and owner account will be created
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(CompanyType)

    class Meta:
        form_class = ValidCompanyForm

    @transaction.atomic
    def mutate_and_get_payload(self, info, **input):
        user_input = {
            'email': input.get('working_email'),
            'phone': input.get('contact'),
            'role': RoleTypeChoices.COMPANY_OWNER,
            'password': input.get('password'),
            'first_name': input.get('first_name'),
            'post_code': input.get('post_code')
        }
        user, error_data = _perform_user_registration(
            info, user_input, RoleTypeChoices.COMPANY_OWNER, 
            profile_form=ValidCompanyForm, profile_input=input
        )
        if error_data:
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        
        return ValidCompanyMutation(
            success=True, message="Successfully added", instance=user.company
        )


class VendorMutation(DjangoFormMutation):
    """
        Users can create valid Vendor information through a form input.\n
        and owner account will be created
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorType)

    class Meta:
        form_class = VendorSignupForm

    @transaction.atomic
    def mutate_and_get_payload(self, info, **input):
        user_input = {
            'email': input.get('email'),
            'phone': input.get('contact'),
            'role': RoleTypeChoices.VENDOR,
            'password': input.get('password'),
            'first_name': input.get('first_name'),
            'last_name': input.get('last_name'),
            'post_code': input.get('post_code')
        }
        user, error_data = _perform_user_registration(
            info, user_input, RoleTypeChoices.VENDOR,
            profile_form=VendorSignupForm, profile_input=input
        )
        if error_data:
            raise_graphql_error_with_fields("Invalid input request.", error_data)

        return VendorMutation(
            success=True, message="Successfully added", instance=user.vendor
        )


class RegisterUser(graphene.Mutation):
    """
    Truly Unified Signup for all roles (Admin, Vendor, Client).
    """
    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        input = SignupFormInput(required=True)

    @transaction.atomic
    def mutate(self, info, input):
        role = input.get('role', RoleTypeChoices.USER)
        user_input = {
            'email': input.get('email'),
            'phone': input.get('phone'),
            'role': role,
            'password': input.get('password'),
            'first_name': input.get('first_name'),
            'last_name': input.get('last_name'),
            'post_code': input.get('post_code'),
            'company_name': input.get('company_name'),
        }
        
        profile_form = None
        profile_input = None
        
        # Decide if we need to create a profile (Vendor/Company)
        if role == RoleTypeChoices.VENDOR and input.get('company_name'):
            profile_form = VendorSignupForm
            profile_input = {
                'name': input.get('company_name'),
                'email': input.get('email'),
                'contact': input.get('phone'),
                'post_code': input.get('post_code')
            }
        elif role == RoleTypeChoices.COMPANY_OWNER and input.get('company_name'):
            profile_form = ValidCompanyForm
            profile_input = {
                'name': input.get('company_name'),
                'working_email': input.get('email'),
                'contact': input.get('phone'),
                'post_code': input.get('post_code')
            }

        user, error_data = _perform_user_registration(
            info, user_input, role, 
            profile_form=profile_form, profile_input=profile_input
        )
        
        if error_data:
            raise_graphql_error_with_fields("Signup failed.", error_data)

        return RegisterUser(success=True, message="Registration successful", user=user)


class VendorUpdateMutation(DjangoModelFormMutation):
    """
        Users can create valid Vendor information through a form input.\n
        and owner account will be created
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorType)

    class Meta:
        form_class = VendorUpdateForm

    @transaction.atomic
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        if user.is_admin:
            obj = Vendor.objects.get(id=input['id'])
        else:
            obj = user.vendor
            # Protect sensitive fields from non-admin updates
            input.pop('is_popular', None)
            input.pop('is_featured', None)
            input.pop('is_blocked', None)
            input.pop('commission_percentage', None)
        form = VendorUpdateForm(data=input, instance=obj)
        error_data = {}
        if form.is_valid():
            obj = form.save()
        else:
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return VendorUpdateMutation(
            success=True, message="Successfully updated", instance=obj
        )


def _get_valid_areas_from_ids(info, valid_area_ids):
    areas = []
    for gid in valid_area_ids or []:
        node = None
        try:
            node = graphene.relay.Node.get_node_from_global_id(info, str(gid))
        except Exception:
            pass
        if node is None or not isinstance(node, ValidArea):
            try:
                node = ValidArea.objects.filter(pk=int(gid)).first()
            except (TypeError, ValueError):
                node = None
        if node is None or not isinstance(node, ValidArea):
            raise_graphql_error("One or more area IDs are invalid.", "invalid_valid_area_id")
        if node.is_active:
            areas.append(node)
    return areas


VALID_DELIVERY_DAYS = {"su", "mo", "tu", "we", "th", "fr", "sa"}
DEFAULT_NOTIFICATION_PREFERENCES = {
    "newOrders": True,
    "orderUpdates": True,
    "reviewsAndRatings": True,
    "promotionsAndTips": True,
    "emailNotifications": True,
}
DEFAULT_REGION_CURRENCY = "NOK"
DEFAULT_LANGUAGE = "en"
DEFAULT_TIME_ZONE = "UTC"


def _validate_non_negative(value, field_name):
    if value is not None and value < 0:
        raise_graphql_error("Value must be zero or greater.", field_name)
    return value


def _normalise_delivery_days(days):
    invalid_days = [day for day in days or [] if day not in VALID_DELIVERY_DAYS]
    if invalid_days:
        raise_graphql_error("Please select valid delivery days.", "deliveryDays")
    return days or []


def _normalise_delivery_time_slots(time_slots):
    normalised = []
    for slot in time_slots or []:
        start = slot.get("start")
        end = slot.get("end")
        if not start or not end:
            raise_graphql_error("Time slot start and end are required.", "deliveryTimeSlots")
        normalised.append({"start": start, "end": end})
    return normalised


def _sync_delivery_mode(settings, input_data):
    if input_data.get("delivery_mode"):
        if settings.delivery_mode == VendorDeliverySettings.DELIVERY:
            settings.delivery_available = True
            settings.pickup_available = False
        elif settings.delivery_mode == VendorDeliverySettings.PICKUP:
            settings.delivery_available = False
            settings.pickup_available = True
        elif settings.delivery_mode == VendorDeliverySettings.BOTH:
            settings.delivery_available = True
            settings.pickup_available = True
        return

    if "delivery_available" in input_data or "pickup_available" in input_data:
        if settings.delivery_available and settings.pickup_available:
            settings.delivery_mode = VendorDeliverySettings.BOTH
        elif settings.delivery_available:
            settings.delivery_mode = VendorDeliverySettings.DELIVERY
        elif settings.pickup_available:
            settings.delivery_mode = VendorDeliverySettings.PICKUP


def apply_delivery_settings_input(settings, input_data):
    delivery_mode = input_data.get("delivery_mode")
    if delivery_mode and delivery_mode not in dict(VendorDeliverySettings.DELIVERY_MODE_CHOICES):
        raise_graphql_error("Please select a valid delivery mode.", "deliveryMode")

    nullable_fields = ["pickup_address", "pickup_instructions", "free_delivery_over"]
    scalar_fields = [
        "delivery_mode",
        "delivery_available",
        "pickup_available",
        "base_delivery_fee",
        "same_fee_all_distances",
        "max_deliveries_per_day",
        "max_orders_per_time_slot",
        "min_delivery_time",
        "max_delivery_time",
    ]
    for field in nullable_fields:
        if field in input_data:
            setattr(settings, field, input_data.get(field))
    for field in scalar_fields:
        if field in input_data and input_data.get(field) is not None:
            setattr(settings, field, input_data.get(field))

    settings.base_delivery_fee = _validate_non_negative(settings.base_delivery_fee, "baseDeliveryFee")
    settings.free_delivery_over = _validate_non_negative(settings.free_delivery_over, "freeDeliveryOver")
    settings.max_deliveries_per_day = _validate_non_negative(
        settings.max_deliveries_per_day,
        "maxDeliveriesPerDay",
    )
    settings.max_orders_per_time_slot = _validate_non_negative(
        settings.max_orders_per_time_slot,
        "maxOrdersPerTimeSlot",
    )
    if "delivery_days" in input_data:
        settings.delivery_days = _normalise_delivery_days(input_data.get("delivery_days"))
    if "delivery_time_slots" in input_data:
        settings.delivery_time_slots = _normalise_delivery_time_slots(input_data.get("delivery_time_slots"))

    _sync_delivery_mode(settings, input_data)
    return settings


def _normalise_business_hours(hours):
    normalised = []
    seen_days = set()
    for day_hours in hours or []:
        day = day_hours.get("day")
        if day not in VALID_DELIVERY_DAYS:
            raise_graphql_error("Please select a valid business day.", "businessHours")
        if day in seen_days:
            raise_graphql_error("Business hours can contain each day only once.", "businessHours")
        seen_days.add(day)

        slots = []
        for slot in day_hours.get("slots") or []:
            start = slot.get("start")
            end = slot.get("end")
            if not start or not end:
                raise_graphql_error("Business hour slot start and end are required.", "businessHours")
            slots.append({"start": start, "end": end})

        normalised.append({
            "day": day,
            "enabled": bool(day_hours.get("enabled")),
            "slots": slots,
        })
    return normalised


def _normalise_notification_preferences(current, preferences):
    data = {**DEFAULT_NOTIFICATION_PREFERENCES, **(current or {})}
    if preferences is None:
        return data

    field_map = {
        "new_orders": "newOrders",
        "order_updates": "orderUpdates",
        "reviews_and_ratings": "reviewsAndRatings",
        "promotions_and_tips": "promotionsAndTips",
        "email_notifications": "emailNotifications",
    }
    for input_key, output_key in field_map.items():
        if input_key in preferences and preferences.get(input_key) is not None:
            data[output_key] = preferences.get(input_key)
    return data


def _validate_established_year(year):
    if year is None:
        return year
    current_year = timezone.now().year
    if year < 1800 or year > current_year:
        raise_graphql_error("Please enter a valid established year.", "establishedYear")
    return year


def _reset_vendor_settings(settings):
    settings.business_description = None
    settings.business_address = None
    settings.organization_number = None
    settings.business_type = None
    settings.established_year = None
    settings.business_hours = []
    settings.notification_preferences = DEFAULT_NOTIFICATION_PREFERENCES.copy()
    settings.language = DEFAULT_LANGUAGE
    settings.region_currency = DEFAULT_REGION_CURRENCY
    settings.time_zone = DEFAULT_TIME_ZONE
    settings.store_connected = True
    return settings


def apply_vendor_settings_input(settings, input_data):
    nullable_fields = [
        "business_description",
        "business_address",
        "organization_number",
        "business_type",
        "established_year",
    ]
    scalar_fields = ["language", "region_currency", "time_zone", "store_connected"]

    for field in nullable_fields:
        if field in input_data:
            setattr(settings, field, input_data.get(field))
    for field in scalar_fields:
        if field in input_data and input_data.get(field) is not None:
            setattr(settings, field, input_data.get(field))

    settings.established_year = _validate_established_year(settings.established_year)
    if "business_hours" in input_data:
        settings.business_hours = _normalise_business_hours(input_data.get("business_hours"))
    if "notification_preferences" in input_data:
        settings.notification_preferences = _normalise_notification_preferences(
            settings.notification_preferences,
            input_data.get("notification_preferences"),
        )
    elif not settings.notification_preferences:
        settings.notification_preferences = DEFAULT_NOTIFICATION_PREFERENCES.copy()
    return settings


class SetVendorServiceAreas(graphene.Mutation):
    """
    Set the list of valid areas (postcodes) where the vendor provides service.
    Only the authenticated vendor can update their own service areas.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorType)

    class Arguments:
        valid_area_ids = graphene.List(graphene.ID, required=True)

    @is_authenticated
    def mutate(self, info, valid_area_ids):
        user = info.context.user
        if not getattr(user, 'vendor', None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")
        vendor = user.vendor
        vendor.service_areas.set(_get_valid_areas_from_ids(info, valid_area_ids))
        return SetVendorServiceAreas(
            success=True,
            message="Service areas updated.",
            instance=vendor,
        )


class DeliveryTimeSlotInput(graphene.InputObjectType):
    start = graphene.String(required=True)
    end = graphene.String(required=True)


class VendorDeliverySettingsInput(graphene.InputObjectType):
    delivery_mode = graphene.String()
    delivery_available = graphene.Boolean()
    pickup_available = graphene.Boolean()
    pickup_address = graphene.String()
    pickup_instructions = graphene.String()
    base_delivery_fee = graphene.Decimal()
    free_delivery_over = graphene.Decimal()
    same_fee_all_distances = graphene.Boolean()
    delivery_days = graphene.List(graphene.String)
    delivery_time_slots = graphene.List(DeliveryTimeSlotInput)
    max_deliveries_per_day = graphene.Int()
    max_orders_per_time_slot = graphene.Int()
    min_delivery_time = graphene.Int()
    max_delivery_time = graphene.Int()
    valid_area_ids = graphene.List(graphene.ID)


class VendorDeliverySettingsMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorDeliverySettingsType)

    class Arguments:
        input = VendorDeliverySettingsInput(required=True)

    @is_authenticated
    def mutate(self, info, input):
        user = info.context.user
        if not getattr(user, "vendor", None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")

        delivery_settings, _ = VendorDeliverySettings.objects.get_or_create(vendor=user.vendor)
        delivery_settings = apply_delivery_settings_input(delivery_settings, input)
        delivery_settings.save()
        if input.get("valid_area_ids") is not None:
            user.vendor.service_areas.set(_get_valid_areas_from_ids(info, input.get("valid_area_ids")))

        return VendorDeliverySettingsMutation(
            success=True,
            message="Delivery settings updated.",
            instance=delivery_settings,
        )


class VendorKitchenStatusUpdate(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorType)

    class Arguments:
        is_kitchen_active = graphene.Boolean(required=True)

    @is_authenticated
    def mutate(self, info, is_kitchen_active):
        user = info.context.user
        if not getattr(user, "vendor", None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")
        user.vendor.is_kitchen_active = is_kitchen_active
        user.vendor.save()
        return VendorKitchenStatusUpdate(
            success=True,
            message="Kitchen status updated.",
            instance=user.vendor,
        )


class BusinessHourSlotInput(graphene.InputObjectType):
    start = graphene.String(required=True)
    end = graphene.String(required=True)


class BusinessDayHoursInput(graphene.InputObjectType):
    day = graphene.String(required=True)
    enabled = graphene.Boolean(required=True)
    slots = graphene.List(BusinessHourSlotInput)


class NotificationPreferencesInput(graphene.InputObjectType):
    new_orders = graphene.Boolean()
    order_updates = graphene.Boolean()
    reviews_and_ratings = graphene.Boolean()
    promotions_and_tips = graphene.Boolean()
    email_notifications = graphene.Boolean()


class VendorSettingsInput(graphene.InputObjectType):
    business_description = graphene.String()
    business_address = graphene.String()
    organization_number = graphene.String()
    business_type = graphene.String()
    established_year = graphene.Int()
    business_hours = graphene.List(BusinessDayHoursInput)
    notification_preferences = graphene.Argument(NotificationPreferencesInput)
    language = graphene.String()
    region_currency = graphene.String()
    time_zone = graphene.String()
    store_connected = graphene.Boolean()


class VendorSettingsMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorSettingsType)

    class Arguments:
        input = VendorSettingsInput(required=True)

    @is_authenticated
    def mutate(self, info, input):
        user = info.context.user
        if not getattr(user, "vendor", None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")

        settings, _ = VendorSettings.objects.get_or_create(vendor=user.vendor)
        settings = apply_vendor_settings_input(settings, input)
        settings.save()
        return VendorSettingsMutation(
            success=True,
            message="Vendor settings updated.",
            instance=settings,
        )


class VendorSettingsReset(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorSettingsType)

    @is_authenticated
    def mutate(self, info):
        user = info.context.user
        if not getattr(user, "vendor", None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")

        settings, _ = VendorSettings.objects.get_or_create(vendor=user.vendor)
        settings = _reset_vendor_settings(settings)
        settings.save()
        return VendorSettingsReset(
            success=True,
            message="Vendor settings reset.",
            instance=settings,
        )


class VendorStoreDisconnect(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorSettingsType)

    @is_authenticated
    def mutate(self, info):
        user = info.context.user
        if not getattr(user, "vendor", None):
            raise_graphql_error("Vendor profile not found.", "vendor_required")

        settings, _ = VendorSettings.objects.get_or_create(vendor=user.vendor)
        settings.store_connected = False
        settings.save()
        return VendorStoreDisconnect(
            success=True,
            message="Store disconnected.",
            instance=settings,
        )


class SetVendorCommission(graphene.Mutation):
    """
    Admin can set platform commission (%) for a specific vendor.
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(VendorType)

    class Arguments:
        id = graphene.ID(required=True)
        commission_percentage = graphene.Int(required=False)

    @is_admin_user
    def mutate(self, info, id, commission_percentage=None):
        vendor = Vendor.objects.filter(id=id).last()
        if not vendor:
            raise_graphql_error("Vendor not found.", field_name="id")
        if commission_percentage is None:
            vendor.commission_percentage = None
        else:
            if commission_percentage < 0 or commission_percentage > 100:
                raise_graphql_error("Commission percentage must be between 0 and 100.", field_name="commissionPercentage")
            vendor.commission_percentage = commission_percentage
        vendor.save()
        return SetVendorCommission(
            success=True,
            message="Successfully updated",
            instance=vendor,
        )


class VendorDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id):
        try:
            obj = Vendor.objects.get(id=id, is_deleted=False)
            obj.name = f"deleted_{obj.id} {obj.name}"
            obj.email = f"deleted_{obj.id}_{obj.email}"
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            for user in obj.users.all():
                user.is_active = False
                user.is_expired = True
                user.is_deleted = True
                user.deleted_on = timezone.now()
                user.deactivation_reason = None
                user.email = f"deleted_{user.id}_{user.email}"
                user.username = f"deleted_{user.id}_{user.username}"
                user.deleted_phone = user.phone
                user.phone = None
                user.save()
            return VendorDelete(
                success=True,
                message="Successfully deleted",
            )
        except Vendor.DoesNotExist:
            raise_graphql_error("Vendor not found.", "vendor_not_exist")


class CompanyBlockUnBlock(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)
        note = graphene.String()

    @is_admin_user
    def mutate(self, info, id, note=""):
        try:
            obj = Company.objects.get(id=id)
            if obj.is_blocked:
                obj.is_blocked = False
                msg = "unblocked"
            else:
                obj.is_blocked = True
                msg = "blocked"
            obj.note = note
            obj.save()
            return CompanyBlockUnBlock(
                success=True,
                message=f"Successfully {msg}",
            )
        except Company.DoesNotExist:
            raise_graphql_error("Company not found.", "company_not_exist")


class CompanyDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id):
        try:
            obj = Company.objects.get(id=id, is_deleted=False)
            obj.name = f"deleted_{obj.id} {obj.name}"
            obj.working_email = f"deleted_{obj.id}_{obj.working_email}"
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            for user in obj.users.all():
                user.is_active = False
                user.is_expired = True
                user.is_deleted = True
                user.deleted_on = timezone.now()
                user.deactivation_reason = None
                user.email = f"deleted_{user.id}_{user.email}"
                user.username = f"deleted_{user.id}_{user.username}"
                user.deleted_phone = user.phone
                user.phone = None
                user.save()
            return CompanyDelete(
                success=True,
                message="Successfully deleted",
            )
        except Company.DoesNotExist:
            raise_graphql_error("Company not found.", "company_not_exist")


class ChangeCompanyStatus(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)
        status = graphene.String(required=True)
        note = graphene.String()

    @is_admin_user
    def mutate(self, info, id, status, note=""):
        try:
            obj = Company.objects.get(id=id, is_deleted=False)
            obj.status = status
            obj.note = note
            obj.save()
            return ChangeCompanyStatus(
                success=True,
                message="Successfully updated",
            )
        except Company.DoesNotExist:
            raise_graphql_error("Company not found.", "company_not_exist")


class VendorBlockUnBlock(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)
        note = graphene.String()

    @is_admin_user
    def mutate(self, info, id, note=""):
        try:
            obj = Vendor.objects.get(id=id)
            if obj.is_blocked:
                obj.is_blocked = False
                msg = "unblocked"
            else:
                obj.is_blocked = True
                msg = "blocked"
            obj.note = note
            obj.save()
            return VendorBlockUnBlock(
                success=True,
                message=f"Successfully {msg}",
            )
        except Vendor.DoesNotExist:
            raise_graphql_error("Vendor not found.", "company_not_exist")


class VendorWithdrawRequest(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        status = graphene.String()
        withdraw_amount = graphene.Decimal()
        note = graphene.String()

    @is_authenticated
    def mutate(self, info, id=None, status="", withdraw_amount=0, note=""):
        user = info.context.user
        if user.is_admin:
            obj = WithdrawRequest.objects.get(id=id)
            if status not in WithdrawRequestChoices:
                raise_graphql_error("Status not valid.", field_name="status")
            
            old_status = obj.status
            obj.status = status
            obj.note = note
            
            PAID_WITHDRAW_STATUSES = [
                WithdrawRequestChoices.ACCEPTED,
                WithdrawRequestChoices.COMPLETED,
            ]
            
            # Update withdrawn_amount based on status transitions to prevent double-counting
            if status in PAID_WITHDRAW_STATUSES and old_status not in PAID_WITHDRAW_STATUSES:
                obj.vendor.withdrawn_amount += obj.withdraw_amount
                obj.vendor.save()
            elif status not in PAID_WITHDRAW_STATUSES and old_status in PAID_WITHDRAW_STATUSES:
                obj.vendor.withdrawn_amount -= obj.withdraw_amount
                obj.vendor.save()
                
            obj.save()
            msg = 'updated'
        else:
            if not user.is_vendor:
                raise_graphql_error("User not permitted.")
            vendor = user.vendor
            if not withdraw_amount or withdraw_amount > vendor.balance:
                raise_graphql_error("Amount is not available.", field_name="withdraw_amount")
            WithdrawRequest.objects.create(vendor=vendor, withdraw_amount=withdraw_amount, note=note)
            msg = 'added'
        return VendorWithdrawRequest(
            success=True,
            message=f"Successfully {msg}",
        )


# class CompanyOwnerRegistration(graphene.Mutation):
#     """
#     """
#
#     success = graphene.Boolean()
#     message = graphene.String()
#     user = graphene.Field(UserType)
#
#     class Arguments:
#         company = graphene.ID()
#         note = graphene.String()



class CompanyOwnerRegistration(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        company = graphene.ID()

    @is_admin_user
    def mutate(
            self,
            info,
            company,
            **kwargs
    ) -> object:
        company = Company.objects.get(id=company)
        errors = {}
        input = {
            'email': company.working_email,
            'phone': company.contact,
            'post_code': company.post_code,
            'role': RoleTypeChoices.COMPANY_OWNER
        }
        form = UserRegistrationForm(data=input)
        if form.is_valid() and not errors:
            company.save()
            user = User.objects.create_user(**input)
            user.company = company
            user.save()
            user.send_email_verified()
        else:
            error_data = errors
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return CompanyOwnerRegistration(
            success=True,
            message="User registration was successful.",
            user=user
        )


class UserCreationMutation(DjangoModelFormMutation):
    """
        This mutation will provide ability to update user data.
        partial update also allowed in this mutation.
        Gender choice::
        1. male
        2. female
        3. other
    """
    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    class Meta:
        form_class = UserCreationForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input) -> object:
        user = info.context.user
        company = user.company
        if not user.company or user.role not in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            raise_graphql_error("User not permitted to this operation.")
        error_data = {}
        if user.role == RoleTypeChoices.COMPANY_MANAGER and input.get('role') not in [RoleTypeChoices.COMPANY_EMPLOYEE]:
            error_data['role'] = 'Selected role is not valid.'
        elif input.get('role') not in [RoleTypeChoices.COMPANY_EMPLOYEE, RoleTypeChoices.COMPANY_MANAGER]:
            error_data['role'] = 'Selected role is not valid.'
        form = UserCreationForm(data=input)
        if form.data.get('id'):
            obj = User.objects.get(id=form.data['id'])
            form = UserCreationForm(data=input, instance=obj)
        form_data = form.data
        if form.is_valid() and not error_data:
            allergies = form_data.pop('allergies', [])
            if form_data.get('id'):
                User.objects.filter(id=form_data['id']).update(**form_data)
                obj = User.objects.get(id=form_data['id'])
            else:
                obj = User.objects.create_user(**form_data)
                obj.company = company
                obj.save()
                obj.send_email_verified()
            obj.allergies.clear()
            obj.allergies.add(*Ingredient.objects.filter(id__in=allergies))
        else:
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        UnitOfHistory.user_history(
            action=HistoryActions.USER_CREATE,
            user=user,
            perform_for=obj,
            request=info.context
        )
        return UserCreationMutation(
            success=True, message="Successfully added", user=obj
        )


class AddressMutation(DjangoModelFormMutation):
    """
    """
    instance = graphene.Field(AddressType)
    success = graphene.Boolean()
    message = graphene.String()

    class Meta:
        form_class = AddressForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input) -> object:
        user = info.context.user
        error_data = {}
        if user.is_admin:
            if input.get('company'):
                try:
                    Company.objects.get(id=input.get('company'))
                except Exception:
                    error_data['company'] = "This field is required."
        elif user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            if user.company:
                input['company'] = user.company.id
        elif user.role == RoleTypeChoices.USER:
            # For clients, we link the address to the user directly
            input['user'] = user.id
        else:
            raise_graphql_error("User not permitted for this operation.")
        form = AddressForm(data=input)
        if input.get('id'):
            if user.is_admin:
                form = AddressForm(data=input, instance=Address.objects.get(id=input.get('id')))
            else:
                if user.role == RoleTypeChoices.USER:
                    form = AddressForm(data=input, instance=Address.objects.get(id=input.get('id'), user=user))
                else:
                    form = AddressForm(
                        data=input, instance=Address.objects.get(id=input.get('id'), company=user.company))
        if not error_data and form.is_valid():
            obj = form.save()
        else:
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return AddressMutation(
            success=True, instance=obj, message="Successfully updated"
        )


class AddressDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_company_user
    def mutate(self, info, id):
        try:
            obj = Address.objects.get(id=id, is_deleted=False, company=info.context.user.company)
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            return AddressDelete(
                success=True,
                message="Successfully deleted",
            )
        except Address.DoesNotExist:
            raise_graphql_error("Address not found.", "address_not_exist")


class CompanyBillingAddressMutation(DjangoFormMutation):
    """
    """
    instance = graphene.Field(CompanyBillingAddressType)
    success = graphene.Boolean()
    message = graphene.String()

    class Meta:
        form_class = CompanyBillingAddressForm

    @is_company_user
    def mutate_and_get_payload(self, info, **input) -> object:
        user = info.context.user
        form = CompanyBillingAddressForm(data=input)
        try:
            form = CompanyBillingAddressForm(data=input, instance=CompanyBillingAddress.objects.get(company=user.company))
        except Exception:
            pass
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = user.company
            obj.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return CompanyBillingAddressMutation(
            success=True, instance=obj, message="Successfully updated"
        )


class UserMutation(graphene.Mutation):
    """
    Standard mutation to update user profile settings.
    """
    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        input = graphene.Argument(lambda: UserProfileInput)

    @is_authenticated
    def mutate(self, info, input):
        user = info.context.user
        
        # Extract data from input
        for field, value in input.items():
            if field == 'allergies':
                user.allergies.set(Ingredient.objects.filter(id__in=value))
            elif hasattr(user, field):
                setattr(user, field, value)
        
        user.save()
        
        return UserMutation(
            success=True, 
            message="Profile updated successfully", 
            user=user
        )

class UserProfileInput(graphene.InputObjectType):
    first_name = graphene.String()
    last_name = graphene.String()
    secondary_email = graphene.String()
    phone = graphene.String()
    work_phone = graphene.String()
    company_name = graphene.String()
    job_title = graphene.String()
    industry_usage = graphene.String()
    gender = graphene.String()
    post_code = graphene.Int()
    notification_preferences = GenericScalar()
    allergies = graphene.List(graphene.ID)

class UserAccountMutation(DjangoModelFormMutation):
    """
    """
    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    class Meta:
        form_class = UserAccountForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input) -> object:
        user = info.context.user
        form = UserAccountForm(data=input, instance=user)
        old_data = get_object_dict(user, list(UserAccountForm().fields.keys()))
        new_data = None
        if form.is_valid():
            obj = User.objects.get(id=user.id)
            current_password = form.cleaned_data.pop('current_password', "")
            password = form.cleaned_data.pop('password', "")
            obj.username = form.cleaned_data.get('username', user.username)
            if current_password:
                if not obj.check_password(current_password):
                    raise_graphql_error("Wrong password given.", "invalid_password")
                validate_password(password)
                obj.set_password(password)
            obj.save()
            new_data = get_object_dict(User.objects.get(id=user.id), list(UserAccountForm().fields.keys()))
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        UnitOfHistory.user_history(
            action=HistoryActions.USER_UPDATE,
            old_meta=old_data,
            new_meta=new_data,
            user=user,
            request=info.context
        )
        return UserAccountMutation(
            success=True, user=obj, message="Successfully updated"
        )


class LoginUser(graphene.Mutation):
    """
    User Login Mutation::
    user will be able to log in by email and password
    will get
        1. access_token as access
        2. user data
        3. success status as bool true or false
    """

    success = graphene.Boolean()
    access = graphene.String()
    refresh = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        role = graphene.String()
        activate = graphene.Boolean()

    def mutate(
            self,
            info,
            email,
            password,
            role=None,
            activate=False
    ) -> object:
        user = signup(info.context, str(email).strip(), password, activate)

        # Role-based panel restriction
        if role and user.role != role:
            raise_graphql_error(
                message=f"This account is registered as a {user.role}. Please login through the correct panel.",
                code="invalid_role_portal"
            )

        access = TokenManager.get_access({"user_id": str(user.id)})
        mac_address = info.context.headers.get("macaddress", None)
        if user.is_admin:
            access_token = AccessToken.objects.filter(user=user, mac_address=mac_address).last()
            if not access_token:
                access_token = AccessToken.objects.create(user=user, mac_address=mac_address)
            else:
                AccessToken.objects.filter(user=user, mac_address=mac_address).exclude(id=access_token.id).delete()
            access_token.token = access
            access_token.save()
        else:
            AccessToken.objects.create_or_update(user=user, token=access, mac_address=mac_address)
        return LoginUser(
            access=access,
            user=user,
            success=True
        )


class ToggleRewardsMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    enabled = graphene.Boolean()

    @is_authenticated
    def mutate(self, info):
        user = info.context.user
        user.rewards_enabled = not user.rewards_enabled
        user.save()
        return ToggleRewardsMutation(
            success=True, 
            message=f"Rewards {'enabled' if user.rewards_enabled else 'disabled'}",
            enabled=user.rewards_enabled
        )


class InviteFriendMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        email = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, email):
        return InviteFriendMutation(success=True, message=f"Invitation sent to {email}")


class RedeemRewardMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    remaining_points = graphene.Int()

    class Arguments:
        points = graphene.Int(required=True)
        redeem_type = graphene.String(required=True) # 'credit' or 'amazon'

    @is_authenticated
    def mutate(self, info, points, redeem_type):
        from .models import RewardTransaction
        user = info.context.user
        
        if not user.rewards_enabled:
            raise GraphQLError("Rewards are currently disabled for your account.")
            
        if user.reward_points < points:
            raise GraphQLError(f"Insufficient points. You have {user.reward_points} points.")
            
        if points < 2500 and redeem_type == 'amazon':
            raise GraphQLError("Minimum 2,500 points required for Amazon Gift Card.")
            
        user.reward_points -= points
        user.save()
        
        RewardTransaction.objects.create(
            user=user,
            transaction_type=RewardTransaction.SPEND,
            source=RewardTransaction.SOURCE_ORDER if redeem_type == 'credit' else RewardTransaction.SOURCE_REFERRAL,
            points=points,
            description=f"Redeemed for {redeem_type}"
        )
        
        return RedeemRewardMutation(
            success=True, 
            message=f"Successfully redeemed {points} points for {redeem_type}.",
            remaining_points=user.reward_points
        )


class SocialLogin(graphene.Mutation):
    """
        User will be able to sign in via social accounts like, facebook, google and apple etc.
        And apple user have to pass id_token.\n
        And a history will be added for user social login.
    """

    success = graphene.Boolean()
    access = graphene.String()
    refresh = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        social_type = graphene.String(required=True)
        social_id = graphene.String(required=True)
        email = graphene.String()
        first_name = graphene.String()
        last_name = graphene.String()
        id_token = graphene.String()  # only for apple
        activate = graphene.Boolean()
        need_verification = graphene.Boolean()

    def mutate(
            self,
            info,
            social_type,
            social_id,
            email,
            first_name=None,
            last_name=None,
            id_token=None,
            need_verification=False,
            activate=False
    ):
        if not email and id_token and social_type == 'apple':
            email = TokenManager.get_email(id_token)

        user = social_signup(
            info.context,
            social_type,
            social_id,
            email,
            first_name=first_name,
            last_name=last_name,
            activate=activate,
            verification=need_verification
        )
        mac_address = info.context.headers.get("macaddress", None)
        access = TokenManager.get_access({"user_id": str(user.id)})
        refresh = TokenManager.get_refresh({"user_id": str(user.id)})
        access_token = AccessToken.objects.filter(user=user, mac_address=mac_address).last()
        if access_token:
            access_token.token = access
            access_token.save()
            AccessToken.objects.filter(user=user, mac_address=mac_address).exclude(id=access_token.id).delete()
        else:
            access_token = AccessToken.objects.create(user=user, token=access, mac_address=mac_address)
        return SocialLogin(
            access=access,
            refresh=refresh,
            user=user,
            success=True
        )


class ExpiredAllToken(graphene.Mutation):
    """
    Logout Mutation::
    to expire all token from this system.
    """

    success = graphene.Boolean()
    message = graphene.String()

    @is_authenticated
    def mutate(self, info):
        user = info.context.user
        user.is_expired = True
        user.save()
        AccessToken.objects.filter(user=user).delete()
        UserDeviceToken.objects.filter(user=user).delete()
        return ExpiredAllToken(
            message="Successfully Logout",
            success=True
        )


class PasswordChange(graphene.Mutation):
    """
    Password Change Mutation::
    Password change by using old password.
    password length should min 8.
    not similar to username or email.
    password must contain number
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        old_password = graphene.String(required=True)
        new_password = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, old_password, new_password):
        user = info.context.user
        if not user.check_password(old_password):
            raise_graphql_error("Wrong password given.", "invalid_password")
        if old_password == new_password:
            raise_graphql_error("New password should not be same as old password.", "invalid_password")
        validate_password(new_password)
        user.set_password(new_password)
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_CHANGE,
            user=user,
            request=info.context
        )
        return PasswordChange(
            success=True,
            message="Password successfully changed",
            user=user
        )


class PasswordResetMail(graphene.Mutation):
    """
        Password Rest Mail mutation::
        User will be able to Request Rest their password.
        by using register email.
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        email = graphene.String(required=True)
        role = graphene.String()

    def mutate(self, info, email, role=None):
        user = User.objects.filter(email=email).first()
        if not user:
            raise_graphql_error("No user is associated with this email address.", "invalid_email")
        
        # Role-based check
        if role and user.role != role:
            raise_graphql_error(
                message=f"This email is not associated with a {role} account.",
                code="invalid_role"
            )

        pin = generate_pin()
        ResetPassword.objects.update_or_create(user=user, defaults={"token": pin})

        context = {
            'user_name': user.full_name,
            'pin': pin,
            'year': timezone.now().year
        }
        template = 'emails/reset_password1.html'
        subject = 'Password Reset PIN'
        send_email_on_delay.delay(template, context, subject, email)
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_RESET_REQUEST,
            user=user,
            request=info.context
        )
        return PasswordResetMail(
            success=True,
            message="OTP has been sent to your email"
        )


class VerifyResetCode(graphene.Mutation):
    """
    Verify the 4-digit PIN sent via email.
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        email = graphene.String(required=True)
        pin = graphene.String(required=True)

    def mutate(self, info, email, pin):
        if not ResetPassword.objects.check_pin(pin, email):
            raise_graphql_error("Invalid or expired PIN code!", "invalid_pin")
        
        return VerifyResetCode(success=True, message="PIN verified successfully.")


class EmailVericationMail(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        email = graphene.String(required=True)

    def mutate(self, info, email):
        user = User.objects.filter(email=email).first()
        if not user:
            raise_graphql_error("No user is associated with this email address.", "invalid_email")
        user.send_email_verification()
        UnitOfHistory.user_history(
            action=HistoryActions.RESEND_ACTIVATION,
            user=user,
            request=info.context
        )
        return EmailVericationMail(
            success=True,
            message="Verification mail was sent successfully"
        )


class PasswordReset(graphene.Mutation):
    """
    Password Rest Mutation::
    after getting rest mail user will
    get a link to reset password.
    To verify Password:
        1. password length should min 8.
        2. not similar to username or email.
        3. password must contain number
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        email = graphene.String(required=True)
        token = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)

    def mutate(
            self,
            info,
            email,
            token,
            password1,
            password2
    ):
        user = User.objects.filter(email=email).first()
        if not user:
            raise_graphql_error("No user is associate with this email.", "invalid_email")
        validate_password(password1)
        if not password1 == password2:
            raise_graphql_error("Password does not match.", "invalid_password")
        if not ResetPassword.objects.checkKey(token, email):
            raise_graphql_error("Token is not valid or expired!", "invalid_token")
        user.set_password(password2)
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_RESET,
            user=user,
            request=info.context
        )
        return PasswordReset(
            success=True,
            message="Password reset successful",
        )


class UserPasswordReset(graphene.Mutation):
    """
    Password Rest Mutation::
    after getting rest mail user will
    get a link to reset password.
    To verify Password:
        1. password length should min 8.
        2. not similar to username or email.
        3. password must contain number
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)
        password = graphene.String(required=True)

    @is_authenticated
    def mutate(
            self,
            info,
            id,
            password
    ):
        logged_user = info.context.user
        if logged_user.is_admin:
            user = User.objects.filter(id=id).first()
        elif logged_user.role in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            user = User.objects.filter(id=id, company=logged_user.company).first()
        else:
            user = User.objects.filter(id=None).first()
        if not user:
            raise_graphql_error("No user is associate with this email.", "invalid_email")
        validate_password(password)
        user.set_password(password)
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_RESET,
            user=logged_user,
            perform_for=user,
            request=info.context
        )
        return UserPasswordReset(
            success=True,
            message="Password reset successful",
        )


class PasswordResetAdmin(graphene.Mutation):
    """
    Password Rest Mutation::
    after getting rest mail user will
    get a link to reset password.
    To verify Password:
        1. password length should min 8.
        2. not similar to username or email.
        3. password must contain number
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        user = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)

    @is_admin_user
    def mutate(
            self,
            info,
            user,
            password1,
            password2
    ):
        user = User.objects.filter(id=user).first()
        if not user:
            raise_graphql_error("No user found.")
        validate_password(password1)
        if not password1 == password2:
            raise_graphql_error("Password does not match.", "invalid_password")
        user.set_password(password2)
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_RESET,
            user=info.context.user,
            perform_for=user,
            request=info.context
        )
        return PasswordResetAdmin(
            success=True,
            message="Password reset successful",
        )


class PasswordResetCompany(graphene.Mutation):
    """
    Password Rest Mutation::
    after getting rest mail user will
    get a link to reset password.
    To verify Password:
        1. password length should min 8.
        2. not similar to username or email.
        3. password must contain number
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        user = graphene.String(required=True)
        password1 = graphene.String(required=True)
        password2 = graphene.String(required=True)

    @is_company_user
    def mutate(
            self,
            info,
            user,
            password1,
            password2
    ):
        logged_user = info.context.user
        user = User.objects.filter(id=user, company=logged_user.company).first()
        if not user:
            raise_graphql_error("No user found.")
        validate_password(password1)
        if not password1 == password2:
            raise_graphql_error("Password does not match.", "invalid_password")
        user.set_password(password2)
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.PASSWORD_RESET,
            user=logged_user,
            perform_for=user,
            request=info.context
        )
        return PasswordResetCompany(
            success=True,
            message="Password reset successful",
        )


class ProfilePictureUpload(graphene.Mutation):
    """
    Upload Profile Picture Mutation::
    user will be able to upload their profile picture.
    after upload picture will be automatically cropped.
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        photo_url = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, photo_url):
        user = info.context.user
        user.photo_url = photo_url
        user.photo_uploaded_at = timezone.now()
        user.is_profile_photo_verified = False
        user.rejection_reason_profile_photo = None
        user.save()
        # profile_photo_verification.delay(str(user.id))  # send profile photo verification notification
        UnitOfHistory.user_history(
            action=HistoryActions.PROFILE_PICTURE_UPLOAD,
            user=user,
            request=info.context
        )
        return ProfilePictureUpload(
            success=True,
            message="profile picture uploaded successfully",
            user=user
        )


class ProfileDeactivation(graphene.Mutation):
    """
    Account Deactivation Mutation::
    User will be able to deactivate their profile.
    by putting reason why want to deactivate.
    """

    message = graphene.String()
    success = graphene.Boolean()
    user = graphene.Field(UserType)

    class Arguments:
        reason = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, reason):
        user = info.context.user
        user.is_active = False
        user.deactivation_reason = reason
        user.is_expired = True
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.ACCOUNT_DEACTIVATE,
            user=user,
            request=info.context
        )
        return ProfileDeactivation(
            success=True,
            message="Deactivation successful"
        )


class DeviceToken(graphene.Mutation):
    """
    User Device Token::
    every user will have a device token it could be
    web-browser or mobile device token. to trigger fmc notification.
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        device_type = graphene.String(required=True)
        device_token = graphene.String(required=True)

    @is_authenticated
    def mutate(
            self,
            info,
            device_type,
            device_token,
    ):
        user = info.context.user
        mac_address = info.context.headers.get("macaddress", None)
        if user.is_driver:
            if not mac_address:
                raise_graphql_error("Mac address not detected.")
        UserDeviceToken.objects.filter(device_type=device_type, device_token=device_token).exclude(user=user).delete()
        UserDeviceToken.objects.filter(user=user).update(is_current=False)
        UserDeviceToken.objects.update_or_create(
            user=user, defaults={
                "device_type": device_type, "device_token": device_token, "mac_address": mac_address,
                'is_current': True
            }
        )
        return DeviceToken(
            success=True, user=user,
            message="Token added successfully"
        )





class VerifyAccess(graphene.Mutation):
    """
    Verify Mutation::
    to verify user access.
    """

    success = graphene.Boolean()
    message = graphene.String()

    @is_authenticated
    def mutate(self, info, **kwargs):
        return VerifyAccess(
            success=True,
            message="User has access."
        )


class UserBlockUnBlock(graphene.Mutation):
    """
    if admin want to control user access.
    they can block and unblock user.
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        email = graphene.String(required=True)

    @is_admin_user
    def mutate(self, info, email):
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                user.is_active = False
                user.is_expired = True
                msg = "blocked"
                act = HistoryActions.USER_BLOCKED
            else:
                user.is_active = True
                msg = "unblocked"
                act = HistoryActions.USER_UNBLOCKED
            user.deactivation_reason = None
            user.save()
            UnitOfHistory.user_history(
                action=act,
                user=info.context.user,
                request=info.context,
                perform_for=user
            )
            return UserBlockUnBlock(
                success=True,
                message=f"Successfully {msg}",
                user=user
            )
        except User.DoesNotExist:
            raise_graphql_error("User not found.", "user_not_exist")


class UserDelete(graphene.Mutation):
    """
    if admin want to control user access.
    they can block and unblock user.
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Arguments:
        email = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, email):
        try:
            logged_in_user = info.context.user
            if logged_in_user.is_admin:
                user = User.objects.get(email=email)
            elif logged_in_user.role in [RoleTypeChoices.COMPANY_OWNER]:
                user = User.objects.get(email=email, company=logged_in_user.company)
                try:
                    carts = user.cart_items.annotate(
                        due=F('cart__price_with_tax') * (100 - F('cart__order__company_allowance')) / 100 - F(
                            'paid_amount'))
                    due = round(carts.aggregate(total_due=Sum('due'))['total_due'], 2)
                    if due:
                        raise_graphql_error("User has pending payment.")
                except Exception:
                    pass
            else:
                raise_graphql_error("User not permitted.", "not_permitted")
            user.is_active = False
            user.is_expired = True
            user.is_deleted = True
            user.deleted_on = timezone.now()
            user.deactivation_reason = None
            user.username = f"deleted_{user.id}_{user.username}"
            user.email = f"deleted_{user.id}_{email}"
            user.deleted_phone = user.phone
            user.phone = None
            user.save()
            msg = "deleted"
            act = HistoryActions.USER_DELETED
            UnitOfHistory.user_history(
                action=act,
                user=info.context.user,
                request=info.context,
                perform_for=user
            )
            return UserDelete(
                success=True,
                message=f"Successfully {msg}",
                user=user
            )
        except User.DoesNotExist:
            raise_graphql_error("User not found.", "user_not_exist")


class VerifyProfilePicture(graphene.Mutation):
    """
        While Verify profile photo Admin have to choose action
        like approve or reject. if reject have to
        reason of rejection.
        action::
            1. approved
            2. rejected
    """

    message = graphene.String()
    success = graphene.Boolean()
    user = graphene.Field(UserType)

    class Arguments:
        action = graphene.String(required=True)
        reason = graphene.String()
        email = graphene.String(required=True)

    @is_admin_user
    def mutate(self, info, email, action, reason=None):
        if action not in [VerifyActionChoices.APPROVED, VerifyActionChoices.REJECTED]:
            raise_graphql_error("Please Choose between 'approved' or 'rejected'.", "invalid_action")
        try:
            user = User.objects.get(email=email)
            if user.photo_url:
                if action == VerifyActionChoices.APPROVED and not reason:
                    user.is_profile_photo_verified = True
                    user.rejection_reason_profile_photo = None
                    act = HistoryActions.PROFILE_PICTURE_VERIFIED
                elif action == VerifyActionChoices.REJECTED and not reason:
                    raise_graphql_error("Reason is required for rejection.", "reason_required")
                elif action == VerifyActionChoices.REJECTED and reason:
                    user.is_profile_photo_verified = False
                    user.rejection_reason_profile_photo = reason
                    act = HistoryActions.PROFILE_PICTURE_REJECTED
                else:
                    raise_graphql_error("Invalid credential.", "invalid_credential")
                user.save()
                # profile_photo_verification.delay(str(user.id))  # send profile photo verification notification
                UnitOfHistory.user_history(
                    action=act,
                    user=info.context.user,
                    request=info.context,
                    perform_for=user
                )
                return VerifyProfilePicture(
                    user=user,
                    success=True,
                    message=f"Successfully {'verified' if not reason else 'rejected'}"
                )
            raise_graphql_error("Photo not uploaded.", "no_photo")
        except User.DoesNotExist:
            raise_graphql_error("User not found.", "user_not_exist")


class AddAdministrator(DjangoModelFormMutation):
    """
        Will take email, username and password as required fields.
        And super_user field to define whether admin super-user or staff user.
    """

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)

    class Meta:
        form_class = AdminRegistrationForm

    @is_super_admin
    def mutate_and_get_payload(self, info, **input):
        roles = [
            RoleTypeChoices.SUB_ADMIN, RoleTypeChoices.DEVELOPER, RoleTypeChoices.EDITOR,
            RoleTypeChoices.SEO_MANAGER, RoleTypeChoices.SYSTEM_MANAGER
        ]
        form = AdminRegistrationForm(data=input)
        if input.get('id'):
            form = AdminRegistrationForm(
                data=input, instance=User.objects.get(id=input.get('id'), role__in=roles))
        if form.is_valid():
            if form.cleaned_data.get('role') not in roles:
                raise_graphql_error("Select a valid choice.", field_name="role")
            super_user = form.cleaned_data.pop('super_user', False)
            if not input.get('id'):
                try:
                    validate_password(form.cleaned_data['password'])
                except Exception as e:
                    raise_graphql_error_with_fields("Invalid request.", errors={'password': list(e)})
                user = User.objects.create_user(**form.cleaned_data)
                user.email_verification(form.cleaned_data['password'])
            else:
                del form.cleaned_data['password']
                user = User.objects.get(id=input.get('id'))
                User.objects.filter(id=user.id).update(**form.cleaned_data)
            # if super_user:
            #     user.is_staff = True
            #     user.is_superuser = super_user
            user.is_staff = super_user
            user.is_superuser = super_user
            user.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        UnitOfHistory.user_history(
            action=HistoryActions.NEW_ADMIN_ADDED,
            user=info.context.user,
            perform_for=user,
            request=info.context
        )
        return AddAdministrator(
            message="New administrator successfully added.",
            success=True,
            user=user
        )


class AgreementMutation(DjangoModelFormMutation):
    """
        Admins can create and update agreement information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    agreement = graphene.Field(AgreementType)

    class Meta:
        form_class = AgreementForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = AgreementForm(data=input)
        object_id = None
        if form.data.get('object_id'):
            object_id = form.data['object_id']
            obj = get_object_by_attrs(
                Agreement, {'id': object_id}, {'name': 'objectId', 'value': object_id})
            form = AgreementForm(data=input, instance=obj)
        form.data['user'] = user
        if form.is_valid():
            del form.cleaned_data['object_id']
            obj, created = Agreement.objects.update_or_create(id=object_id, defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        UnitOfHistory.user_history(
            action=HistoryActions.AGREEMENT_ADDED if created else HistoryActions.AGREEMENT_UPDATED,
            user=info.context.user,
            request=info.context
        )
        return AgreementMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", agreement=obj
        )


class AcceptAgreementMutation(graphene.Mutation):
    """
    This Mutation will register user action
    for accept Terms and Conditions and Privacy Policy
    in action have to pass
        1. terms-and-conditions
        2. privacy-policy
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        action = graphene.String(required=True)

    @is_authenticated
    def mutate(self, info, action):
        user = info.context.user
        if action == 'terms-and-conditions':
            user.term_and_condition_accepted = True
            action = HistoryActions.ACCEPTED_TERMS_AND_CONDITIONS
        elif action == 'privacy-policy':
            user.privacy_policy_accepted = True
            action = HistoryActions.ACCEPTED_PRIVACY_POLICY
        else:
            raise_graphql_error(f"Select a valid choice. '{action}' is not one of the available choices.")
        user.save()
        UnitOfHistory.user_history(
            action=action,
            user=user,
            request=info.context
        )
        return AcceptAgreementMutation(
            success=True,
            message="Successfully Created"
        )


class DefaultMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        name = graphene.String(required=True)
        slogan = graphene.String()
        contact = graphene.String()
        email = graphene.String()
        default_vendor_commission_percentage = graphene.Int()
        logo_url = graphene.String()
        cover_photo_url = graphene.String()
        logo_file_id = graphene.String()
        cover_photo_file_id = graphene.String()
        address = graphene.String()
        formation_date = graphene.Date()
        social_media_links = graphene.JSONString()

    @is_admin_user
    def mutate(self, info, **input):
        client = ClientDetails.objects.last()
        if not client:
            client, _ = ClientDetails.objects.get_or_create(id=1)
        ClientDetails.objects.filter(id=client.id).update(**input)
        return DefaultMutation(
            success=True,
            message="Successfully updated"
        )


class CouponMutation(DjangoModelFormMutation):
    """
        Admins can create and update Promo Code information through a form input.\n
        promoType choices::
        1. flat
        2. percentage
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(CouponType)

    class Meta:
        form_class = CouponForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        errors = {}
        form = CouponForm(data=input)
        if form.data.get('id'):
            obj = get_object_by_id(Coupon, form.data['id'])
            form = CouponForm(data=input, instance=obj)
        if form.data.get("start_date") >= form.data.get("end_date"):
            errors['startDate'] = "Start-date should be less than end-date."
        if form.is_valid() and not errors:
            added_for = form.cleaned_data.pop('added_for', [])
            obj, created = Coupon.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
            obj.added_for.clear()
            obj.added_for.add(*added_for)
        else:
            error_data = errors
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return CouponMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class CouponDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id):
        try:
            obj = Coupon.objects.get(id=id, is_deleted=False)
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            return CouponDelete(
                success=True,
                message="Successfully deleted",
            )
        except Coupon.DoesNotExist:
            raise_graphql_error("Coupon not found.", "coupon_not_exist")


class WithdrawRequestDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id):
        try:
            obj = WithdrawRequest.objects.get(id=id, is_deleted=False)
            if obj.status in [WithdrawRequestChoices.PENDING, WithdrawRequestChoices.CANCELLED]:
                obj.delete()
            else:
                obj.is_deleted = True
                obj.deleted_on = timezone.now()
                obj.save()
            return WithdrawRequestDelete(
                success=True,
                message="Successfully deleted",
            )
        except WithdrawRequest.DoesNotExist:
            raise_graphql_error("Coupon not found.", "coupon_not_exist")


class ApplyCouponMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()
    data = graphene.Field(AppliedCouponType)

    class Arguments:
        coupon = graphene.String()
        price = graphene.Float()

    @is_authenticated
    def mutate(self, info, coupon, price, **kwargs):
        user = info.context.user
        try:
            coupon, amount_discounted, discounted_price = Coupon.get_promo_and_apply(
                user, coupon, price)
        except Exception as e:
            error = list(map(str, e))
            raise GraphQLError(
                message="Invalid promo-code.",
                extensions={
                    "errors": {"coupon": error}
                }
            )
        discounted_value = coupon.value if coupon.promo_type == coupon.FLAT else f"{coupon.value}%"
        data = AppliedCouponType(
            actual_price=price,
            amount_discounted=amount_discounted or 0,
            discounted_price=discounted_price,
            discounted_value=discounted_value
        )
        return ApplyCouponMutation(
            success=True, message="Successfully applied", data=data
        )


class Mutation(graphene.ObjectType):
    """
        define all the mutations by identifier name for query
    """
    company_mutation = CompanyMutationForAdmin.Field()
    create_company = CompanyMutation.Field()
    valid_create_company = ValidCompanyMutation.Field()
    company_block_unblock = CompanyBlockUnBlock.Field()
    company_delete = CompanyDelete.Field()
    company_status_change = ChangeCompanyStatus.Field()
    register_company_owner = CompanyOwnerRegistration.Field()
    register_user = RegisterUser.Field()
    create_company_staff = UserCreationMutation.Field()
    address_mutation = AddressMutation.Field()
    address_delete = AddressDelete.Field()
    company_billing_address_mutation = CompanyBillingAddressMutation.Field()
    vendor_creation = VendorMutation.Field()
    vendor_update = VendorUpdateMutation.Field()
    set_vendor_service_areas = SetVendorServiceAreas.Field()
    vendor_delivery_settings_mutation = VendorDeliverySettingsMutation.Field()
    vendor_kitchen_status_update = VendorKitchenStatusUpdate.Field()
    vendor_settings_mutation = VendorSettingsMutation.Field()
    vendor_settings_reset = VendorSettingsReset.Field()
    vendor_store_disconnect = VendorStoreDisconnect.Field()
    set_vendor_commission = SetVendorCommission.Field()
    vendor_block_unblock = VendorBlockUnBlock.Field()
    vendor_delete = VendorDelete.Field()
    withdraw_request_mutation = VendorWithdrawRequest.Field()
    withdraw_request_delete = WithdrawRequestDelete.Field()

    # reset_password_company_staff = PasswordResetCompany.Field()

    login_user = LoginUser.Field()
    social_login = SocialLogin.Field()
    logout = ExpiredAllToken.Field()
    password_change = PasswordChange.Field()
    password_reset_mail = PasswordResetMail.Field()
    verify_reset_code = VerifyResetCode.Field()
    send_verification_mail = EmailVericationMail.Field()
    reset_password = PasswordReset.Field()

    general_profile_update = UserMutation.Field()
    account_profile_update = UserAccountMutation.Field()
    upload_profile_picture = ProfilePictureUpload.Field()
    account_deactivate = ProfileDeactivation.Field()
    device_token = DeviceToken.Field()

    has_user_access = VerifyAccess.Field()

    reset_password_by_admin = PasswordResetAdmin.Field()
    user_block_or_unblock = UserBlockUnBlock.Field()
    user_delete = UserDelete.Field()
    profile_picture_verification = VerifyProfilePicture.Field()
    add_new_administrator = AddAdministrator.Field()

    agreement_mutation = AgreementMutation.Field()
    accept_agreement_mutation = AcceptAgreementMutation.Field()
    default_mutation = DefaultMutation.Field()
    coupon_mutation = CouponMutation.Field()
    coupon_delete = CouponDelete.Field()
    # Reward Mutations
    toggle_rewards = ToggleRewardsMutation.Field()
    invite_friend = InviteFriendMutation.Field()
    redeem_reward = RedeemRewardMutation.Field()
    # apply_coupon = ApplyCouponMutation.Field()
