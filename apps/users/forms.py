from django import forms

# local imports
from .models import (
    Address,
    Agreement,
    Company,
    CompanyBillingAddress,
    Coupon,
    User,
    Vendor,
)


class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'secondary_email',
            'phone',
            'work_phone',
            'company_name',
            'job_title',
            'industry_usage',
            'notification_preferences',
        ]


class UserCreationForm(forms.ModelForm):

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'phone',
            'email',
            'gender',
            'date_of_birth',
            'role',
            'photo_url',
            'file_id',
            'allergies',
        ]


class UserCreateForm(forms.ModelForm):
    # password = forms.CharField(required=False)
    id = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'phone',
            'email',
            'gender',
            'date_of_birth',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password") and not self.cleaned_data.get('id'):
            user.set_password(self.cleaned_data["password"])
            user.is_verified = True
            user.is_email_verified = True
        if commit:
            user.save()
        return user


class UserAccountForm(forms.ModelForm):
    current_password = forms.CharField(required=False)
    password = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'password',
        ]


class UserRegistrationForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ("email", "phone", 'role')


class UserRegisterForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ("email", "phone", 'role', 'password')


class SignupForm(forms.ModelForm):
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    password = forms.CharField()
    post_code = forms.IntegerField(required=False)
    name = forms.CharField(required=False)  # For Vendor or Company name

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "password", "post_code", "role")


class AdminRegistrationForm(forms.ModelForm):
    super_user = forms.BooleanField(required=False)
    password = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password", 'role')


class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ("name", "description", "email", "working_email", 'contact', 'post_code')


class CompanyUpdateForm(forms.ModelForm):
    first_name = forms.CharField()
    address = forms.CharField(required=False)

    class Meta:
        model = Company
        exclude = (
            "is_checked", "status", "note", "is_deleted", "deleted_on", "ordered_amount",
            "invoice_amount", "paid_amount"
        )


class ValidCompanyForm(forms.ModelForm):
    first_name = forms.CharField()
    password = forms.CharField()

    class Meta:
        model = Company
        fields = ("name", "description", "email", "working_email", 'contact', 'post_code')


class VendorForm(forms.ModelForm):
    first_name = forms.CharField()
    password = forms.CharField()

    class Meta:
        model = Vendor
        fields = ("name", "email", 'contact', 'post_code')


class VendorSignupForm(forms.ModelForm):

    class Meta:
        model = Vendor
        fields = ("name", "email", "contact", "post_code")


class VendorUpdateForm(forms.ModelForm):
    id = forms.CharField(required=True)

    class Meta:
        model = Vendor
        fields = (
            "name", "email", 'contact', 'post_code', 'logo_url', 'file_id', 'formation_date', 'social_media_links',
            'is_blocked',
            'commission_percentage',
        )


class AgreementForm(forms.ModelForm):
    object_id = forms.IntegerField(required=False)

    class Meta:
        model = Agreement
        fields = '__all__'


class CouponForm(forms.ModelForm):

    class Meta:
        model = Coupon
        exclude = ("is_deleted", "deleted_on")


class AddressForm(forms.ModelForm):
    company = forms.ModelChoiceField(queryset=Company.objects.all(), required=False)
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Address
        fields = [
            'company', 'user', 'address_type', 'location_name', 'address', 
            'unit_floor', 'city', 'state', 'post_code', 'phone', 
            'receiving_name', 'instruction', 'default'
        ]


class CompanyBillingAddressForm(forms.ModelForm):

    class Meta:
        model = CompanyBillingAddress
        exclude = ("company",)
