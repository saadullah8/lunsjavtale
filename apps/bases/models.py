
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """Define all common fields for all table with id field."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )  # generate unique id.
    created_on = models.DateTimeField(
        auto_now_add=True
    )  # object creation time. will automatically generate
    updated_on = models.DateTimeField(
        auto_now=True
    )  # object update time. will automatically generate

    class Meta:
        abstract = True  # define this table/model is abstract


class BaseWithoutID(models.Model):
    """Define all common fields for all table."""

    created_on = models.DateTimeField(
        auto_now_add=True
    )  # object creation time. will automatically generate
    updated_on = models.DateTimeField(
        auto_now=True
    )  # object update time. will automatically generate

    class Meta:
        abstract = True  # define this table/model is abstract


class SoftDeletion(models.Model):
    """Define all common fields for all table."""
    is_deleted = models.BooleanField(default=False)
    deleted_on = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        abstract = True  # define this table/model is abstract


class BasePriceModel(models.Model):
    actual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        default=1
    )
    tax_percent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        # blank=True,
        null=True,
        default=15
    )
    price_with_tax = models.DecimalField(
        _("Final price"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="price adding TAX",
        # blank=True,
        null=True
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.tax_percent = self.tax_percent or settings.TAX_PERCENTAGE
        # self.price_with_tax = self.actual_price + ((self.tax_percent * self.actual_price) / 100)
        self.actual_price = self.price_with_tax * 100 / (100 + self.tax_percent)
        super(BasePriceModel, self).save(*args, **kwargs)
