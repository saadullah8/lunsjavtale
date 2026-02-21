from django.conf import settings
from django.db import models

from apps.bases.models import BasePriceModel, BaseWithoutID, SoftDeletion
from apps.scm.choices import (
    MeetingStatusChoices,
    MeetingTypeChoices,
    ProductStatusChoices,
)


class Ingredient(BaseWithoutID, SoftDeletion):
    """
    """
    name = models.CharField(max_length=64)  # define ingredient name
    description = models.TextField(
        blank=True, null=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_ingredients"  # define table name for database
        ordering = ['-id']  # define default order as id in descending

    @classmethod
    def queryset(cls):
        return cls.objects.filter(is_deleted=False)


class CategoryManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Category(BaseWithoutID, SoftDeletion):
    """
        Store category information by making a hierarchy of category and sub-category
    """
    name = models.CharField(max_length=64)  # define category name
    description = models.TextField(
        blank=True, null=True,
        help_text="Category description for showing over page."
    )
    parent = models.ForeignKey(
        to='self', on_delete=models.SET_NULL, related_name='children', blank=True, null=True
    )  # define the category for any sub-category
    # slug = models.SlugField(blank=True, null=True, unique=True, max_length=96)
    logo_url = models.TextField(
        blank=True, null=True
    )
    file_id = models.TextField(
        blank=True, null=True
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=1)

    objects = CategoryManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_categories"  # define table name for database
        verbose_name_plural = 'Categories'
        ordering = ['order', '-created_on']  # define default order as id in descending
        unique_together = ('name', 'parent')

    @classmethod
    def queryset(cls):
        return cls.objects.filter(is_deleted=False)


class WeeklyVariantManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class WeeklyVariant(BaseWithoutID, SoftDeletion):
    """
        Store category information by making a hierarchy of category and sub-category
    """
    name = models.CharField(max_length=64)  # define category name
    description = models.TextField(
        blank=True, null=True,
    )
    days = models.JSONField()
    is_active = models.BooleanField(default=True)

    objects = WeeklyVariantManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_weekly_variant"  # define table name for database


class ProductManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Product(BaseWithoutID, BasePriceModel, SoftDeletion):
    """
        product posting minimum required fields will define here
    """
    name = models.CharField(max_length=128)  # name of the product
    title = models.CharField(max_length=128, blank=True, null=True)  # title of the product
    description = models.TextField()  # some details about the product
    category = models.ForeignKey(
        to=Category, on_delete=models.SET_NULL, related_name='products', null=True
    )  # define the category of the product
    weekly_variants = models.ManyToManyField(
        to=WeeklyVariant, related_name='products', blank=True
    )  # define the weekly_variant of the product
    vendor = models.ForeignKey(
        to='users.Vendor', on_delete=models.SET_NULL, related_name='products', null=True, blank=True
    )  # define the category of the product
    contains = models.JSONField(blank=True, null=True)
    ingredients = models.ManyToManyField(to=Ingredient, blank=True)
    availability = models.BooleanField(default=True)  # if it is available or not
    discount_availability = models.BooleanField(default=True)  # if discount available or not
    visitor_count = models.PositiveIntegerField(default=0, null=True)  # store product visits
    is_adjustable_for_single_staff = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=8, choices=ProductStatusChoices.choices, default=ProductStatusChoices.APPROVED)
    note = models.TextField(blank=True, null=True)

    objects = ProductManager()

    class Meta:
        db_table = f"{settings.DB_PREFIX}_products"  # define table name for database
        ordering = ['order', '-created_on']  # define default order as id in descending
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        # unique_together = ('title', 'category')

    def __str__(self):
        return f"{self.name}"

    @classmethod
    def queryset(cls):
        return cls.objects.filter(is_deleted=False)


class ProductAttachment(models.Model):
    product = models.ForeignKey(to=Product, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.TextField()
    file_id = models.TextField(null=True)
    is_cover = models.BooleanField(default=False)
    created_on = models.DateTimeField(
        auto_now_add=True
    )  # object creation time. will automatically generate

    class Meta:
        db_table = f"{settings.DB_PREFIX}_product_attachments"  # define table name for database
        ordering = ['-id']

    def save(self, *args, **kwargs):
        if self.is_cover:
            self.product.attachments.exclude(id=self.pk).update(is_cover=False)
        if not self.product.attachments.filter(is_cover=True).exists():
            self.is_cover = True
        super(ProductAttachment, self).save(*args, **kwargs)


class FoodMeeting(BaseWithoutID):
    """
        food meeting minimum required fields will define here
    """
    title = models.CharField(max_length=128)  # name of the meeting
    description = models.TextField()  # some details about the meeting
    meeting_type = models.CharField(
        max_length=32, choices=MeetingTypeChoices.choices, default=MeetingTypeChoices.IN_PERSON
    )
    status = models.CharField(
        max_length=32, choices=MeetingStatusChoices.choices, default=MeetingStatusChoices.PENDING
    )
    note = models.TextField(blank=True, null=True)
    meeting_time = models.DateTimeField()
    topics = models.ManyToManyField(
        to=Category, blank=True
    )  # define the category of the meeting
    attendees = models.ManyToManyField(
        to='users.User', blank=True
    )

    company = models.ForeignKey(
        to='users.Company', on_delete=models.SET_NULL, related_name='meetings', null=True, blank=True
    )  # define the category of the product
    company_name = models.CharField(max_length=128, blank=True, null=True)
    first_name = models.CharField(max_length=128, blank=True, null=True)
    last_name = models.CharField(max_length=128, blank=True, null=True)
    email = models.EmailField(max_length=128, blank=True, null=True)
    phone = models.CharField(max_length=16, blank=True, null=True)

    class Meta:
        db_table = f"{settings.DB_PREFIX}_food_meetings"  # define table name for database
        ordering = ['-id']  # define default order as created in descending


class FavoriteProduct(BaseWithoutID):
    added_by = models.ForeignKey(
        to='users.User', on_delete=models.DO_NOTHING, related_name='user_favorites'
    )
    product = models.ForeignKey(to='scm.Product', on_delete=models.DO_NOTHING, related_name='favorites')

    class Meta:
        db_table = f"{settings.DB_PREFIX}_fav_products"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
