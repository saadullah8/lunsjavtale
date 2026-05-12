from django import forms
from django.contrib.auth import get_user_model

from apps.users.models import Vendor
from .models import Category, FoodMeeting, Ingredient, Product, WeeklyVariant

User = get_user_model()


class ProductForm(forms.ModelForm):
    """
        Product model form will define here
    """
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_deleted=False),
        required=True,
        empty_label="Select supplier",
    )

    class Meta:
        model = Product
        exclude = [
            'is_deleted', 'deleted_on', 'visitor_count', 'ingredients', 'actual_price', 'order', 'note', 'status'
        ]


class VendorProductForm(forms.ModelForm):
    """
        Product model form will define here
    """

    class Meta:
        model = Product
        exclude = [
            'is_deleted', 'deleted_on', 'visitor_count', 'vendor', 'availability', 'discount_availability',
            'ingredients', 'actual_price', 'order', 'is_featured', 'status', 'note', "weekly_variants",
            'product_type', 'menu_status', 'pricing_type', 'minimum_guests', 'min_lead_time_hours',
            'available_days', 'blackout_dates', 'dietary_tags', 'custom_dietary', 'optional_add_ons',
        ]


class CategoryForm(forms.ModelForm):
    """
        category model form will define here
    """

    class Meta:
        model = Category
        exclude = ['is_deleted', 'deleted_on']


class FoodMeetingForm(forms.ModelForm):
    """
        Food Meeting model form will define here
    """

    class Meta:
        model = FoodMeeting
        exclude = ['status', 'note']


class IngredientForm(forms.ModelForm):
    """
        Ingredient model form will define here
    """

    class Meta:
        model = Ingredient
        fields = '__all__'


class WeeklyVariantForm(forms.ModelForm):
    """
        WeeklyVariant model form will define here
    """

    class Meta:
        model = WeeklyVariant
        fields = '__all__'
