from django.conf import settings
from django.db import models

from apps.bases.models import BaseWithoutID


class ValidArea(BaseWithoutID):
    name = models.CharField(
        max_length=128, blank=True, null=True
    )
    post_code = models.PositiveIntegerField(unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_valid_areas"  # define table name for database
        ordering = ['-id']  # define default order as id in descending

    def __str__(self):
        return f"{self.post_code}"


class TypeOfAddress(BaseWithoutID):
    name = models.CharField(
        max_length=64, unique=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_address_types"  # define table name for database
        verbose_name = "Address Type"
        verbose_name_plural = "Address Types"
        ordering = ['name']

    def __str__(self):
        return self.name


class Language(BaseWithoutID):
    name = models.CharField(
        max_length=32
    )

    class Meta:
        db_table = f"{settings.DB_PREFIX}_languages"  # define table name for database
        ordering = ['-id']  # define default order as id in descending


class FAQCategory(models.Model):
    name = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_faq_categories"  # define table name for database
        verbose_name_plural = "FAQ Categories"


class FAQ(BaseWithoutID):
    category = models.ForeignKey(
        FAQCategory, on_delete=models.DO_NOTHING, related_name='faqs', blank=True, null=True
    )
    question = models.CharField(
        max_length=500
    )
    answer = models.TextField()
    view_count = models.PositiveIntegerField(
        default=0
    )
    is_visible_on_home_page = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_faqs"  # define table name for database

    def __str__(self):
        return self.question


class SupportedBrand(BaseWithoutID):
    name = models.CharField(
        max_length=32, null=True
    )
    site_url = models.TextField(
        blank=True, null=True
    )
    logo_url = models.TextField(
        null=True
    )
    file_id = models.TextField(
        blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_supported_brands"  # define table name for database
        ordering = ['-id']  # define default order as id in descending


class Partner(BaseWithoutID):
    name = models.CharField(
        max_length=32, null=True
    )
    site_url = models.TextField(
        blank=True, null=True
    )
    logo_url = models.TextField(
        null=True
    )
    file_id = models.TextField(
        blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_partners"  # define table name for database
        ordering = ['-id']  # define default order as id in descending


class FollowUs(BaseWithoutID):
    title = models.CharField(
        max_length=32, null=True, blank=True
    )
    link_type = models.CharField(
        max_length=32, null=True
    )
    link = models.TextField()
    photo_url = models.TextField(
        blank=True, null=True
    )
    file_id = models.TextField(
        blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_follow_us"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
        verbose_name_plural = "Follow Us"


class Promotion(BaseWithoutID):
    title = models.CharField(
        max_length=128, null=True
    )
    description = models.TextField()
    photo_url = models.TextField(
        blank=True, null=True
    )
    file_id = models.TextField(
        blank=True, null=True
    )
    product_url = models.TextField(
        blank=True, null=True
    )
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_promotion"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
        verbose_name_plural = "Promotion"


class ContactUs(BaseWithoutID):
    company_name = models.CharField(
        max_length=32, blank=True, null=True
    )
    name = models.CharField(
        max_length=32, blank=True, null=True
    )
    email = models.EmailField(
        max_length=32, blank=True, null=True
    )
    contact = models.CharField(
        max_length=32, blank=True, null=True
    )
    number_of_employees = models.PositiveIntegerField(default=1)
    post_code = models.PositiveIntegerField(default=1)
    message = models.CharField(
        max_length=32, blank=True, null=True
    )
    agree_to_privacy_policy = models.BooleanField(default=False)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_contact_us"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
        verbose_name_plural = "Contact Us"


class WhoUAre(BaseWithoutID):
    role = models.CharField(
        max_length=32, null=True
    )
    title = models.CharField(
        max_length=32, null=True
    )
    description = models.CharField(
        max_length=32, blank=True, null=True
    )
    additional_info = models.CharField(
        max_length=32, blank=True, null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_who_u_are"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
        verbose_name_plural = "Who U Are"


class WhoUAreAttachment(models.Model):
    who_u_are = models.ForeignKey(to=WhoUAre, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.TextField()
    file_id = models.TextField(null=True)
    is_cover = models.BooleanField(default=False)
    created_on = models.DateTimeField(
        auto_now_add=True
    )  # object creation time. will automatically generate

    class Meta:
        db_table = f"{settings.DB_PREFIX}_who_u_are_attachments"  # define table name for database
        ordering = ['-id']

    def save(self, *args, **kwargs):
        if self.is_cover:
            self.who_u_are.attachments.exclude(id=self.pk).update(is_cover=False)
        super(WhoUAreAttachment, self).save(*args, **kwargs)
