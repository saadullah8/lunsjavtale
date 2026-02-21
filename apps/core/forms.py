from django import forms
from django.contrib.auth import get_user_model

from .models import (
    FAQ,
    ContactUs,
    FAQCategory,
    FollowUs,
    Language,
    Partner,
    Promotion,
    SupportedBrand,
    TypeOfAddress,
    ValidArea,
    WhoUAre,
)

User = get_user_model()


class ValidAreaForm(forms.ModelForm):
    """
        Valid Area model form fields will be defined here
    """

    class Meta:
        model = ValidArea
        fields = "__all__"


class AddressTypeForm(forms.ModelForm):
    """
        Address Type model form fields will be defined here
    """

    class Meta:
        model = TypeOfAddress
        fields = "__all__"


class LanguageForm(forms.ModelForm):
    """
        Language model form will define here
    """

    class Meta:
        model = Language
        fields = '__all__'


class FAQCategoryForm(forms.ModelForm):
    """
        FAQ Category model form will define here
    """

    class Meta:
        model = FAQCategory
        fields = '__all__'


class FAQForm(forms.ModelForm):
    """
        FAQ model form will define here
    """

    class Meta:
        model = FAQ
        exclude = ['view_count']


class SupportedBrandForm(forms.ModelForm):
    """
        Supported Brand model form will define here
    """

    class Meta:
        model = SupportedBrand
        fields = '__all__'


class PartnerForm(forms.ModelForm):
    """
        Partner model form will define here
    """

    class Meta:
        model = Partner
        fields = '__all__'


class FollowUsForm(forms.ModelForm):
    """
        FollowUs model form will define here
    """

    class Meta:
        model = FollowUs
        fields = '__all__'


class PromotionForm(forms.ModelForm):
    """
        Promotion model form will define here
    """

    class Meta:
        model = Promotion
        fields = '__all__'


class ContactUsForm(forms.ModelForm):
    """
        ContactUs model form will define here
    """

    class Meta:
        model = ContactUs
        fields = '__all__'


class WhoUAreForm(forms.ModelForm):
    """
        WhoUAre model form will define here
    """

    class Meta:
        model = WhoUAre
        fields = '__all__'
