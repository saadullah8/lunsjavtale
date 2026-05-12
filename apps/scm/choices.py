from django.db import models


class MeetingTypeChoices(models.TextChoices):
    IN_PERSON = 'in-person'
    INTERVIEW = 'interview'
    REMOTE = 'remote'
    OTHERS = 'others'


class MeetingStatusChoices(models.TextChoices):
    PENDING = 'pending'
    ATTENDED = 'attended'
    POSTPONED = 'postponed'


class ProductStatusChoices(models.TextChoices):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class ProductTypeChoices(models.TextChoices):
    MENU = 'menu'
    ADD_ON = 'add-on'


class MenuStatusChoices(models.TextChoices):
    ACTIVE = 'active'
    DRAFT = 'draft'
    PAUSED = 'paused'


class PricingTypeChoices(models.TextChoices):
    PER_PERSON = 'per-person'
    FIXED_PACKAGE = 'fixed-package'
    TRAY_BASED = 'tray-based'
