import datetime
import decimal

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.bases.models import BaseWithoutID, SoftDeletion
from apps.bases.utils import (
    coupon_validator,
    create_password,
    create_token,
    email_validator,
    set_absolute_uri,
    username_validator,
)
from apps.core.models import ValidArea
from apps.users.choices import (
    AgreementChoices,
    CompanyStatusChoices,
    DeviceTypeChoices,
    GenderChoices,
    RoleTypeChoices,
    SocialAccountTypeChoices,
    WithdrawRequestChoices,
)
from apps.users.managers import (
    UserAccessTokenManager,
    UserManager,
    UserPasswordResetManager,
    UserSocialAccountManager,
)
from apps.users.tasks import send_email_on_delay


class ClientDetails(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    slogan = models.TextField(blank=True, null=True)
    social_media_links = models.JSONField(blank=True, null=True)
    logo_url = models.TextField(
        blank=True,
        null=True
    )
    cover_photo_url = models.TextField(
        blank=True,
        null=True
    )
    logo_file_id = models.TextField(
        blank=True,
        null=True
    )
    cover_photo_file_id = models.TextField(
        blank=True,
        null=True
    )
    address = models.TextField(blank=True, null=True)
    formation_date = models.DateField(blank=True, null=True)
    contact = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=128, blank=True, null=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_client_details"  # define table name for database
        verbose_name_plural = 'Client Details'

    def __str__(self) -> str:
        return str(self.name)


class Company(BaseWithoutID, SoftDeletion):
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField(blank=True, null=True)
    email = models.EmailField(max_length=256, null=True)
    working_email = models.EmailField(max_length=256, unique=True)
    contact = models.CharField(max_length=15, null=True)
    post_code = models.PositiveIntegerField(
        null=True
    )
    allowance_percentage = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)], blank=True)
    is_blocked = models.BooleanField(default=False)
    is_checked = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32, choices=CompanyStatusChoices.choices, default=CompanyStatusChoices.PENDING
    )
    note = models.TextField(blank=True, null=True)
    logo_url = models.TextField(
        blank=True,
        null=True
    )
    file_id = models.TextField(
        blank=True,
        null=True
    )
    no_of_employees = models.PositiveIntegerField(default=1, blank=True)
    formation_date = models.DateField(blank=True, null=True)
    ordered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    invoice_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_company"  # define table name for database
        verbose_name_plural = 'Companies'
        ordering = ['-created_on']  # define default filter as created in descending

    def __str__(self) -> str:
        return str(self.name)

    @property
    def balance(self):
        return self.invoice_amount - self.paid_amount

    @property
    def total_employee(self):
        return self.users.filter(is_deleted=False).count()

    @property
    def owner(self):
        return self.users.filter(role=RoleTypeChoices.COMPANY_OWNER).last()

    @property
    def is_owner_generated(self):
        return self.users.filter(role=RoleTypeChoices.COMPANY_OWNER).exists()

    @property
    def is_valid(self):
        return ValidArea.objects.filter(post_code=self.post_code, is_active=True).exists()


class Vendor(BaseWithoutID, SoftDeletion):
    name = models.CharField(max_length=256, unique=True)
    email = models.EmailField(max_length=256, null=True, unique=True)
    contact = models.CharField(max_length=15, null=True)
    post_code = models.PositiveIntegerField(
        blank=True, null=True
    )
    is_blocked = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
    logo_url = models.TextField(
        blank=True,
        null=True
    )
    file_id = models.TextField(
        blank=True,
        null=True
    )
    formation_date = models.DateField(blank=True, null=True)
    social_media_links = models.JSONField(
        blank=True, null=True
    )
    sold_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    withdrawn_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_vendors"  # define table name for database

    def __str__(self) -> str:
        return str(self.name)

    @property
    def balance(self):
        pending_withdraw = self.withdraw_requests.filter(
            status=WithdrawRequestChoices.PENDING
        ).aggregate(tot=models.Sum('withdraw_amount'))['tot'] or 0
        return self.sold_amount - self.withdrawn_amount - pending_withdraw

    @property
    def owner(self):
        return self.users.last()


class User(BaseWithoutID, AbstractBaseUser, SoftDeletion, PermissionsMixin):
    """Store custom user information.
    all fields are common for all users."""
    username = models.CharField(
        max_length=30,
        validators=[username_validator],
        unique=True,
        null=True
    )  # unique user name to perform username password login.
    email = models.EmailField(
        max_length=100,
        validators=[email_validator],
        unique=True
    )  # unique email to perform email login and send alert mail.
    first_name = models.CharField(
        max_length=150, null=True,
        blank=True
    )
    last_name = models.CharField(
        max_length=150, null=True,
        blank=True
    )
    company = models.ForeignKey(
        to=Company, on_delete=models.SET_NULL, related_name='users',
        blank=True, null=True
    )
    vendor = models.ForeignKey(
        to=Vendor, on_delete=models.SET_NULL, related_name='users',
        blank=True, null=True
    )

    # Verification Check
    is_verified = models.BooleanField(
        default=False
    )
    is_email_verified = models.BooleanField(
        default=False
    )
    is_phone_verified = models.BooleanField(
        default=False
    )
    is_profile_photo_verified = models.BooleanField(
        default=False
    )
    rejection_reason_profile_photo = models.TextField(
        blank=True,
        null=True
    )
    term_and_condition_accepted = models.BooleanField(
        default=False
    )
    privacy_policy_accepted = models.BooleanField(
        default=False
    )

    # permission
    is_active = models.BooleanField(
        default=True
    )
    is_staff = models.BooleanField(
        default=False
    )
    is_superuser = models.BooleanField(
        default=False
    )  # main man of this application.

    # details
    last_active_on = models.DateTimeField(
        default=timezone.now,
        null=True,
        blank=True
    )
    date_joined = models.DateTimeField(
        _('date joined'),
        default=timezone.now
    )
    activation_token = models.UUIDField(
        blank=True,
        null=True
    )
    deactivation_reason = models.TextField(
        null=True,
        blank=True
    )
    is_expired = models.BooleanField(
        default=False
    )  # this flag will define user delete stop this all token for a while

    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Enter Valid Phone number with country code"
    )  # phone number validator.
    phone = models.CharField(
        _("phone number"),
        validators=[phone_regex],
        max_length=15,
        unique=True,
        null=True,
        # blank=True
    )
    deleted_phone = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )
    post_code = models.PositiveIntegerField(
        _("post code"),
        null=True,
        blank=True
    )
    gender = models.CharField(
        max_length=8,
        choices=GenderChoices.choices,
        blank=True,
        null=True
    )
    role = models.CharField(
        max_length=16,
        choices=RoleTypeChoices.choices,
        default=RoleTypeChoices.USER
    )
    job_title = models.CharField(
        max_length=64,
        blank=True, null=True
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True
    )
    address = models.TextField(
        blank=True,
        null=True
    )
    about = models.TextField(
        blank=True,
        null=True
    )
    # Profile Picture
    photo_url = models.TextField(
        blank=True,
        null=True
    )
    file_id = models.TextField(
        blank=True,
        null=True
    )
    photo_uploaded_at = models.DateTimeField(
        blank=True,
        null=True
    )
    allergies = models.ManyToManyField(to='scm.Ingredient', blank=True)
    languages = models.ManyToManyField(to='core.Language', blank=True)

    # last login will provide by django abstract_base_user.
    # password also provide by django abstract_base_user.

    objects = UserManager()

    USERNAME_FIELD = 'email'

    class Meta:
        db_table = f"{settings.DB_PREFIX}_users"  # define table name for database
        ordering = ['-created_on']  # define default filter as created in descending

    def __str__(self) -> str:
        return f"{self.pk}. {self.email}"

    @property
    def full_name(self):
        full_name = ""
        if self.first_name:
            full_name += self.first_name
        if self.last_name:
            full_name += f" {self.last_name}"
        return full_name

    def send_email_verified(self):
        password = create_password()
        self.set_password(password)
        self.is_verified = True
        self.is_email_verified = True
        self.save()
        context = {
            'username': self.username,
            'user_name': self.full_name,
            'email': self.email,
            'password': password,
            'link': settings.SITE_URL,
            'year': timezone.now().year
        }
        if self.role == RoleTypeChoices.COMPANY_MANAGER:
            template = 'emails/manager_verification1.html'
            context['link'] = settings.SITE_URL
            context['company_name'] = self.company.name
        elif self.role == RoleTypeChoices.COMPANY_EMPLOYEE:
            template = 'emails/staff_verification1.html'
            context['link'] = settings.SITE_URL
            context['company_name'] = self.company.name
        elif self.role == RoleTypeChoices.VENDOR:
            template = 'emails/supplier_verification1.html'
            context['link'] = settings.SUPPLIER_SITE_URL
        else:
            template = 'emails/verification1.html'
        subject = 'Email Verification'
        send_email_on_delay.delay(template, context, subject, self.email)  # will add later for sending verification

    def send_email_verification(self):
        token = create_token()
        self.activation_token = token
        self.save()
        link = set_absolute_uri(f"email-verification/?token={token}")
        context = {
            'link': link,
            'user_name': self.full_name,
            'email': self.email,
            'year': timezone.now().year
        }
        template = 'emails/email_verification1.html'
        subject = 'Email Verification'
        send_email_on_delay.delay(template, context, subject, self.email)  # will add later for sending verification

    def email_verification(self, password):
        self.is_verified = True
        self.is_email_verified = True
        self.save()
        context = {
            'username': self.username,
            'user_name': self.full_name,
            'email': self.email,
            'password': password,
            'year': timezone.now().year
        }
        if self.role == RoleTypeChoices.VENDOR:
            template = 'emails/supplier_verification1.html'
            context['link'] = settings.SUPPLIER_SITE_URL
        elif self.role in [
            RoleTypeChoices.ADMIN, RoleTypeChoices.SUB_ADMIN, RoleTypeChoices.SEO_MANAGER, RoleTypeChoices.EDITOR,
            RoleTypeChoices.DEVELOPER, RoleTypeChoices.SYSTEM_MANAGER
        ]:
            template = 'emails/verification1.html'
            context['link'] = settings.ADMIN_SITE_URL
        else:
            template = 'emails/verification1.html'
            context['link'] = settings.SITE_URL
        subject = 'Email Verification'
        send_email_on_delay.delay(template, context, subject, self.email)  # will add later for sending verification

    @property
    def is_admin(self) -> bool:
        return self.is_staff or self.is_superuser

    @property
    def is_vendor(self) -> bool:
        return True if self.vendor else False


class UserSocialAccount(BaseWithoutID):
    social_id = models.CharField(max_length=100)
    social_type = models.CharField(max_length=20, choices=SocialAccountTypeChoices.choices)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    objects = UserSocialAccountManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_social_accounts"  # define table name for database
        unique_together = (("user", "social_type"),)


class UnitOfHistory(models.Model):
    """We will create log for every action
    those data will store in this model"""

    action = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )  # in this field we will define which action was perform.
    created = models.DateTimeField(
        auto_now_add=True
    )
    old_meta = models.JSONField(
        null=True, blank=True
    )  # we store data what was the scenario before perform this action.
    new_meta = models.JSONField(
        null=True, blank=True
    )  # we store data after perform this action.
    header = models.JSONField(
        null=True, blank=True
    )  # request header that will provide user browser
    # information and others details.
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="performer"
    )  # this user will be action performer.
    perform_for = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="perform_for"
    )  # sometime admin/superior  will perform some
    # specific action for employee/or user e.g. payroll change.
    # Generic Foreignkey Configuration. DO NOT CHANGE
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.CharField(
        max_length=100
    )
    content_object = GenericForeignKey()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_unit_of_histories"  # define database table name
        ordering = ['-created']  # define default order as created in descending
        verbose_name_plural = "Unit of histories"

    def __str__(self) -> str:
        return self.action or "action"

    @classmethod
    def user_history(
        cls,
        action,
        user,
        request,
        new_meta=None,
        old_meta=None,
        perform_for=None
    ) -> object:
        try:
            data = {i[0]: i[1] for i in request.META.items() if i[0].startswith('HTTP_')}
        except BaseException:
            data = None
        cls.objects.create(
            action=action,
            user=user,
            old_meta=old_meta,
            new_meta=new_meta,
            header=data,
            perform_for=perform_for,
            content_type=ContentType.objects.get_for_model(User),
            object_id=user.id
        )


class ResetPassword(BaseWithoutID):
    """
    Reset Password will store user data
    who request for reset password.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )
    token = models.UUIDField()

    objects = UserPasswordResetManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_password_reset"
        ordering = ['-id']  # define default order as id in descending


class UserDeviceToken(BaseWithoutID):
    """
    To Tiggerd FMC notification we need
    device token will store user device token
    to triggered notification.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='device_tokens'
    )
    device_token = models.CharField(
        max_length=200
    )
    device_type = models.CharField(
        max_length=8,
        choices=DeviceTypeChoices.choices
    )
    mac_address = models.CharField(max_length=48, null=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_device_tokens"
        ordering = ['-created_on']  # define default order as created in descending

    def save(self, *args, **kwargs):
        super(UserDeviceToken, self).save(*args, **kwargs)
        if self.is_current:
            self.user.device_tokens.filter(is_current=True).exclude(id=self.id).update(is_current=False)
        if UserDeviceToken.objects.filter(device_token=self.device_token):
            UserDeviceToken.objects.filter(device_token=self.device_token).exclude(id=self.id).delete()


class TrackUserLogin(BaseWithoutID):
    username = models.CharField(
        max_length=30, null=True
    )
    email = models.EmailField(
        max_length=100, null=True
    )
    data = models.JSONField(
        null=True
    )  # we store data after perform this action.
    header = models.JSONField(
        null=True
    )  # request header that will provide user browser
    is_success = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_login_tracks"  # define table name for database
        ordering = ['-created_on']  # define default order as created in descending


class AccessToken(BaseWithoutID):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='access_tokens'
    )
    token = models.TextField()
    mac_address = models.CharField(max_length=48, null=True)

    objects = UserAccessTokenManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_access_tokens"  # define table name for database
        ordering = ['-created_on']  # define default order as created in descending


class Address(BaseWithoutID, SoftDeletion):
    """
        company address information will be stored here by address type.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="addresses"
    )
    address_type = models.CharField(
        max_length=64, null=True
    )
    address = models.TextField()
    post_code = models.PositiveIntegerField()
    city = models.CharField(max_length=128, blank=True, null=True)
    state = models.CharField(max_length=128, blank=True, null=True)
    country = models.CharField(max_length=128, blank=True, null=True)
    full_name = models.CharField(max_length=128, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    instruction = models.TextField(blank=True, null=True)
    default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pk}. {self.address}"

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_addresses"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
        verbose_name_plural = "Addresses"

    def save(self, *args, **kwargs):
        if self.default:
            self.company.addresses.exclude(id=self.pk).update(default=False)
        if not self.company.addresses.filter(default=True).exists():
            self.default = True
        super(Address, self).save(*args, **kwargs)


class CompanyBillingAddress(BaseWithoutID):
    """
        billing address information will be stored here by address type.
    """
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="billing_address"
    )
    first_name = models.CharField(max_length=128, null=True, blank=True)
    last_name = models.CharField(max_length=128, null=True, blank=True)
    address = models.TextField()
    sector = models.CharField(max_length=128, blank=True, null=True)
    country = models.CharField(max_length=128, blank=True, null=True)
    phone = models.CharField(max_length=15, null=True, blank=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_company_billing_addresses"  # define table name for database
        verbose_name_plural = "Company Billing addresses"


class Coupon(BaseWithoutID, SoftDeletion):
    FLAT = "flat"
    PERCENTAGE = "percentage"
    TYPE_CHOICES = (
        (FLAT, "flat"),
        (PERCENTAGE, "percentage")
    )

    name = models.CharField(
        max_length=100, unique=True, validators=[coupon_validator])
    promo_type = models.CharField(max_length=100, choices=TYPE_CHOICES)
    max_uses_limit = models.PositiveIntegerField(default=1)
    max_limit_per_user = models.PositiveIntegerField(default=1)
    value = models.PositiveIntegerField()
    min_amount = models.PositiveIntegerField()
    max_amount = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    added_for = models.ManyToManyField(to=Company, blank=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_promo_codes"

    @classmethod
    def get_active_promo_filter(cls):
        today = timezone.now().date()
        filter_q = models.Q(is_active=True, start_date__lte=today, end_date__gte=today)
        return filter_q

    @classmethod
    def get_active_coupons_for_user(cls, user, coupon):
        now = timezone.now()
        today = timezone.now().date()
        promo_delta_time = timezone.now() - datetime.timedelta(minutes=settings.PROMO_DELTA_MINUTES)
        # filter_q = models.Q(is_payment_success=True) | models.Q(is_payment_success=False,
        #                                                         created_on__range=(promo_delta_time, now))
        filter_q = models.Q(created_on__range=(promo_delta_time, now))
        used_count = user.used_coupons.filter(
            coupon__name=coupon).filter(filter_q).count()
        total_count = UserCoupon.objects.filter(coupon__name=coupon).filter(filter_q).count()
        return cls.objects.filter(
            models.Q(added_for__isnull=True) | models.Q(added_for=user.company),
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
            max_limit_per_user__gt=used_count,
            max_uses_limit__gt=total_count
        ).get(name=coupon)

    @classmethod
    def get_promo_and_apply(cls, user, coupon, price):
        if not coupon:
            return None, None, price
        try:
            promo_obj = cls.get_active_coupons_for_user(user, coupon)
            price = decimal.Decimal(price)
            if promo_obj.min_amount > price:
                raise ValidationError(f"Min amount to apply this promo code is {promo_obj.min_amount}.")
            if promo_obj.max_amount and price > promo_obj.max_amount:
                raise ValidationError(
                    f"Max amount for which this promo code can be applied is {promo_obj.max_amount}.")

            return promo_obj, *promo_obj.get_discounted_price(price)
        except cls.DoesNotExist:
            raise ValidationError(settings.COUPON_ERROR_MESSAGE)
        except ValidationError as e:
            raise e

    def get_discounted_price(self, price):
        price = decimal.Decimal(price)
        if self.promo_type == self.FLAT:
            amount_discounted = self.value if self.value < price else price
        else:
            amount_discounted = round((price * decimal.Decimal(self.value / 100)), 2)
        return amount_discounted, price - amount_discounted

    def __str__(self):
        return f"{self.name} : {self.promo_type} - {self.value}"


class UserCoupon(BaseWithoutID):
    coupon = models.ForeignKey(Coupon, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name="used_coupons"
    )
    discounted_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_payment_success = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_user_promo_codes"


class Agreement(BaseWithoutID):
    data = models.TextField(
        blank=True
    )
    type_of = models.CharField(
        max_length=20,
        choices=AgreementChoices.choices,
        unique=True
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_agreements"


class WithdrawRequest(BaseWithoutID, SoftDeletion):
    vendor = models.ForeignKey(
        to=Vendor, on_delete=models.SET_NULL, null=True, related_name='withdraw_requests'
    )
    withdraw_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    status = models.CharField(
        max_length=32, choices=WithdrawRequestChoices.choices, default=WithdrawRequestChoices.PENDING
    )
    note = models.TextField(
        blank=True, null=True
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_withdraw_requests"
