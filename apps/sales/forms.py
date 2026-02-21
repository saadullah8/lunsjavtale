from django import forms
from django.contrib.auth import get_user_model

from .models import BillingAddress, OrderPayment, PaymentMethod, ProductRating

User = get_user_model()


class PaymentMethodForm(forms.ModelForm):
    """
        PaymentMethod model form will define here
    """

    class Meta:
        model = PaymentMethod
        exclude = ['user', 'is_deleted', 'deleted_on']


class ProductRatingForm(forms.ModelForm):
    """
        ProductRating model form will define here
    """

    class Meta:
        model = ProductRating
        exclude = ['added_by']


class BillingAddressForm(forms.ModelForm):
    """
        BillingAddress model form will define here
    """

    class Meta:
        model = BillingAddress
        exclude = ['order']


class OrderPaymentForm(forms.ModelForm):
    """
        BillingAddress model form will define here
    """

    class Meta:
        model = OrderPayment
        exclude = ['created_by', 'payment_info', 'payment_type', 'status', 'is_deleted', 'deleted_on', 'is_checked']


class CompanyOrderPaymentForm(forms.ModelForm):
    """
        BillingAddress model form will define here
    """

    class Meta:
        model = OrderPayment
        exclude = ['created_by', 'payment_info', 'payment_type', 'status', 'is_deleted', 'deleted_on', 'is_checked']
