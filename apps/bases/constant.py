

from django.db import models

ignorable_field_types = [
    str, int, float, bool
]


class VerifyActionChoices(models.TextChoices):
    """
        define selection fields for verify action choice
    """
    APPROVED = 'approved'
    REJECTED = 'rejected'


class ContentTypeModelChoices(models.TextChoices):
    """
        define selection fields for verify action choice
    """
    ADVERTISE = 'BaseAdvertise'
    CATEGORY = 'Category'
    USER = 'User'
    CITY = 'City'


class HistoryActions(models.TextChoices):
    """
        define selection fields for user activity choice
    """
    USER_LOGIN = 'user-login'
    SOCIAL_LOGIN = 'social-login'
    SOCIAL_SIGNUP = 'social-signup'
    ACCEPTED_TERMS_AND_CONDITIONS = 'accepted-terms-and-conditions'
    ACCEPTED_PRIVACY_POLICY = 'accepted-privacy-policy'
    USER_UPDATE = 'user-update'
    USER_CREATE = 'user-create'
    RESEND_ACTIVATION = 'resend-email-activation'
    DOCUMENT_UPLOADED = 'document-uploaded'
    CV_VERIFIED = 'cv-verified'
    CV_REJECTED = 'cv-rejected'
    PROFILE_PICTURE_UPLOAD = 'profile-picture-upload'
    PROFILE_PICTURE_VERIFIED = 'profile-picture-verified'
    PROFILE_PICTURE_REJECTED = 'profile-picture-rejected'
    PASSWORD_CHANGE = 'password-change'
    PASSWORD_RESET_REQUEST = 'password-reset-request'
    PASSWORD_RESET = 'password-reset'
    ACCOUNT_ACTIVATE = 'account-activate'
    ACCOUNT_DEACTIVATE = 'account-deactivate'
    USER_BLOCKED = 'user-access-blocked'
    USER_UNBLOCKED = 'user-access-unblocked'
    USER_DELETED = 'user-deleted'
    COMPANY_ADDED = 'user-company-added'
    COMPANY_UPDATED = 'user-company-updated'
    NEW_ADMIN_ADDED = 'new-admin-added'
    AGREEMENT_ADDED = 'agreement-added'
    AGREEMENT_UPDATED = 'agreement-updated'
    WEBSITE_VISITED = 'website-visited'
    CATEGORY_CREATED = 'category-created'
    CATEGORY_UPDATED = 'category-updated'
    CATEGORY_DELETED = 'category-deleted'


class PropertySellerTypeChoice(models.TextChoices):
    LAND_LORD = 'landlord'
    AGENT = 'agent'


class FrontendField(models.TextChoices):
    TEXT = 'text'
    NUMBER = 'number'
    SELECT = 'select'
    UPLOAD = 'upload'
    CHECKBOX = 'checkbox'
    TEXT_AREA = 'textArea'
    MULTI_TEXT = 'multiText'
    MULTI_UPLOAD = 'multiUpload'
    MULTI_CHECK_BOX = 'multiCheckBox'


class FrequencyTypeChoices(models.TextChoices):
    DAY = 'day'
    WEEK = 'week'
    MONTH = 'month'
