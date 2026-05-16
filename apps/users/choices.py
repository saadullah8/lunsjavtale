
"""All choices for users"""
from django.db import models


class GenderChoices(models.TextChoices):
    """
        define selection choices for gender
    """
    Female = "female"
    Male = "male"
    Other = "other"


class SocialAccountTypeChoices(models.TextChoices):
    """
        define selection choices for social account type
    """
    FACEBOOK = 'facebook'
    LINKEDIN = 'linkedin'
    GOOGLE = 'google'
    APPLE = 'apple'


class DeviceTypeChoices(models.TextChoices):
    """
        define selection choices for device type
    """
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class RoleTypeChoices(models.TextChoices):
    """
        define selection choices for roles
    """
    ADMIN = "admin"
    EDITOR = "editor"
    DEVELOPER = "developer"
    SUB_ADMIN = "sub-admin"
    SEO_MANAGER = "seo-manager"
    SYSTEM_MANAGER = "system-manager"
    USER = "user"
    VENDOR = "vendor"
    COMPANY_OWNER = "company-owner"
    COMPANY_MANAGER = "company-manager"
    COMPANY_EMPLOYEE = "company-employee"


class AgreementChoices(models.TextChoices):
    TERM_AND_CONDITIONS = 'terms-and-conditions'
    PRIVACY_POLICY = 'privacy-policy'
    INSTRUCTION_URL = 'instruction-url'
    ABOUT_US = 'about-us'


class CompanyStatusChoices(models.TextChoices):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class WithdrawRequestChoices(models.TextChoices):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    CANCELLED = 'cancelled'
    COMPLETED = 'completed'
