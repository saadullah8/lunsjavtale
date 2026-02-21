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
