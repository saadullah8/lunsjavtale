
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone

from apps.bases.constant import HistoryActions
from apps.bases.utils import email_checker, raise_graphql_error

from .choices import RoleTypeChoices
from .models import TrackUserLogin, UnitOfHistory, UserSocialAccount

User = get_user_model()


def check_user(user, activate) -> bool:
    """
        check is user admin user or user is active or verified
    """
    if not user.is_admin and not user.is_email_verified:
        raise_graphql_error(message=f"Please verify your email address.({user.email})", code="email_not_verified")
    elif not user.is_active and user.deactivation_reason:
        if activate:
            user.is_active = True
            user.deactivation_reason = None
            user.save()
        else:
            raise_graphql_error(message="Account is deactivated.", code="account_not_active")
    return True


def signup(
        request,
        email,
        password,
        activate=False
) -> object:
    """
        user information will be taken for signup and sign in
    """
    try:
        user = User.objects.get(email=email)
        if not user.is_active:
            raise_graphql_error(message="Account is temporarily blocked.", code='account_blocked')
        user = authenticate(
            username=email,
            password=password
        )
        if not user:
            TrackUserLogin.objects.create(
                email=email, data="Invalid credentials",
                header={i[0]: i[1] for i in request.META.items() if i[0].startswith('HTTP_')}
            )
            raise_graphql_error(message="Invalid credentials", code="invalid_credential")
        if check_user(user, activate):
            user.is_expired = False
            user.last_login = timezone.now()
            user.last_active_on = timezone.now()
            user.save()
            TrackUserLogin.objects.create(
                email=email, data="Successful login", is_success=True,
                header={i[0]: i[1] for i in request.META.items() if i[0].startswith('HTTP_')}
            )
            UnitOfHistory.user_history(
                action=HistoryActions.USER_LOGIN,
                user=user,
                request=request
            )
            return user
    except User.DoesNotExist:
        raise_graphql_error(message="Email is not associated with any existing user.", code="invalid_email")


def social_signup(
    request,
    social_type,
    social_id,
    email,
    first_name=None,
    last_name=None,
    activate=False,
    verification=False
):
    """
        Check social login for user account by social-id,  social-type and email address.
    """
    user_account = UserSocialAccount.objects.filter(
        social_type=social_type,
        social_id=social_id
    ).first()

    if user_account:
        user = user_account.user
        check_user(user, activate)
        user.is_expired = False
        user.last_login = timezone.now()
        user.last_active_on = timezone.now()
        user.save()
        UnitOfHistory.user_history(
            action=HistoryActions.SOCIAL_LOGIN,
            user=user,
            request=request
        )
        return user

    if not email:
        raise_graphql_error("Email is required", "email_not_found")
    elif not email_checker(email):
        raise_graphql_error("Invalid email address", "invalid_email")

    user_exists = User.objects.filter(email=email).first()
    if user_exists:
        user = user_exists
    else:
        # Create new user if not exists
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=RoleTypeChoices.USER,
            is_email_verified=True # Social logins are pre-verified
        )

    UserSocialAccount.objects.create(
        user=user,
        social_id=social_id,
        social_type=social_type
    )

    user.is_email_verified = True
    user.is_expired = False
    user.last_login = timezone.now()
    user.last_active_on = timezone.now()
    user.save()
    UnitOfHistory.user_history(
        action=HistoryActions.SOCIAL_SIGNUP,
        user=user,
        request=request
    )
    return user
