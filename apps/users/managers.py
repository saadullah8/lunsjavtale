
from django.contrib.auth.models import BaseUserManager
from django.utils import timezone

from apps.users.choices import RoleTypeChoices


class UserManager(BaseUserManager):
    def create_base(
        self,
        email,
        password,
        is_staff,
        is_superuser,
        **extra_fields
    ) -> object:
        """
        Create User With Email name password
        """
        if not email:
            raise ValueError("User must have an email")
        user = self.model(
            email=email,
            is_staff=is_staff,
            is_superuser=is_superuser,
            **extra_fields
        )
        if is_superuser:
            user.role = RoleTypeChoices.ADMIN
        user.set_password(password)
        user.save(using=self.db)
        return user

    def create_user(
        self,
        email,
        password=None,
        **extra_fields
    ) -> object:
        """Creates and save non-staff-normal user
        with given email, username and password."""

        return self.create_base(
            email,
            password,
            False,
            False,
            **extra_fields
        )

    def create_superuser(
        self,
        email,
        password,
        **extra_fields
    ) -> object:
        """Creates and saves super user
        with given email, name and password."""
        return self.create_base(
            email,
            password,
            True,
            True,
            **extra_fields
        )

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class UserSocialAccountManager(BaseUserManager):

    def checkSocialAccount(self, social_id, social_type, email):
        if not social_id or not social_type:
            return False
        try:
            if social_type in ['apple', 'facebook']:
                row = self.filter(social_id=social_id, social_type=social_type).latest('updated')
            else:
                row = self.get(social_id=social_id, social_type=social_type, user__email=email)
            return row.user
        except self.model.DoesNotExist:
            return False

    def create_or_update(self, user, social_type, social_id):
        try:
            row = self.get(user=user, social_id=social_id)
            row.social_id = social_id
            row.save()
            return row
        except self.model.DoesNotExist:
            return self.create(user=user, social_type=social_type, social_id=social_id)


class UserPasswordResetManager(BaseUserManager):

    def checkKey(self, token, email):
        """
            check user password reset key if exists
        """
        if not token:
            return False

        try:
            row = self.get(token=token, user__email=email)
            row.delete()
            return True
        except self.model.DoesNotExist:
            return False

    def create_or_update(self, user, token):  # no need to use as django provide update_or_create
        """
            update or create new token
        """
        try:
            row = self.get(user=user)
            row.token = token
            row.save()
            return row
        except self.model.DoesNotExist:
            return self.create(user=user, token=token)


class UserAccessTokenManager(BaseUserManager):  # no need to use as django provide update_or_create

    def create_or_update(self, user, token, mac_address=""):
        """
            update or create new token user account
        """
        try:
            raw = self.get(user=user)
            raw.token = token
            raw.mac_address = mac_address
            raw.save()
            return raw
        except self.model.DoesNotExist:
            return self.create(
                user=user,
                token=token,
                mac_address=mac_address
            )


class UserOTPManager(BaseUserManager):
    """
        check user OTP if Exist
    """
    def check_otp(self, otp, user):
        if not otp:
            return False
        try:
            row = self.get(otp=otp, user=user)
            if row.updated_on + timezone.timedelta(minutes=2) < timezone.now():
                return False
            row.delete()
            return True
        except self.model.DoesNotExist:
            return False

    def create_or_update(self, user, otp):  # no need to use as django provide update_or_create
        try:
            row = self.get(user=user)
            row.otp = otp
            row.save()
            return row
        except self.model.DoesNotExist:
            return self.create(user=user, otp=otp)
