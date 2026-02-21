import datetime

import jwt
from django.conf import settings
from django.utils import timezone


class OldTokenManager:
    """TokenManager Will decode token and
    return access and refresh token"""

    @staticmethod
    def get_token(
        exp,
        payload,
        token_type="access"
    ) -> object:
        # exp = timezone.now().timestamp() + (exp * 60)
        encoded = jwt.encode(
            {
                # "exp": exp,
                "type": token_type,
                **payload
            },
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        if type(encoded) != str:
            return encoded.decode()
        return encoded

    @staticmethod
    def decode_token(token):
        try:
            decoded = jwt.decode(
                token,
                key=settings.SECRET_KEY,
                algorithms="HS256"
            )
        except jwt.DecodeError:
            return None

        # if timezone.now().timestamp() > decoded["exp"]:
        #     return None

        return decoded

    @staticmethod
    def get_access(payload):
        return TokenManager.get_token(5 * 60, payload)

    @staticmethod
    def get_refresh(payload):
        return TokenManager.get_token(24 * 60, payload, "refresh")

    @staticmethod
    def get_email(id_token):
        decoded = jwt.decode(id_token, '', verify=False)
        return decoded.get('email')


class AuthenticationOld:
    def __init__(self, request):
        self.request = request

    def authenticate(self):
        data = self.validate_request()

        if not data:
            return None

        return self.get_user(data["user_id"])

    def channel_auth(self):
        """
            this function will take token from channel request
            and return user data
        """
        data = self.validate_token()
        if not data:
            return None
        return self.get_user(data['user_id'])

    def validate_request(self):
        authorization = self.request.headers.get("AUTHORIZATION", None)

        if not authorization:
            return None

        token = authorization[4:]
        decoded_data = TokenManager.decode_token(token)
        if not decoded_data:
            return None

        return decoded_data

    def validate_token(self):
        """
            this request will be token data
        """
        decoded = TokenManager.decode_token(self.request)
        if not decoded:
            return None
        return decoded

    @staticmethod
    def get_user(user_id):
        from apps.users.models import User

        try:
            user = User.objects.get(id=user_id)
            if not user.is_expired and user.last_active_on > (timezone.now() - datetime.timedelta(days=settings.ACCESS_TOKEN_EXPIRY_LIMIT)):
                user.last_active_on = timezone.now()
                user.save()
                return user
            return None
        except User.DoesNotExist:
            return None


class TokenManager:
    """TokenManager Will decode token and
    return access and refresh token"""

    @staticmethod
    def get_token(
        # exp,
        payload,
        token_type="access"
    ) -> object:
        # exp = timezone.now().timestamp() + (exp * 60)
        encoded = jwt.encode(
            {
                # "exp": exp,
                "type": token_type,
                **payload
            },
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        if type(encoded) != str:
            return encoded.decode()
        return encoded

    @staticmethod
    def decode_token(token):
        try:
            decoded = jwt.decode(
                token,
                key=settings.SECRET_KEY,
                algorithms="HS256"
            )
        except jwt.DecodeError:
            return None

        # if timezone.now().timestamp() > decoded["exp"]:
        #     return None

        return decoded

    @staticmethod
    def get_access(payload):
        return TokenManager.get_token(payload)

    @staticmethod
    def get_refresh(payload):
        return TokenManager.get_token(payload, "refresh")

    @staticmethod
    def get_email(id_token):
        decoded = jwt.decode(id_token, '', verify=False)
        return decoded.get('email')


class Authentication:
    def __init__(self, request):
        self.request = request

    def authenticate(self):
        authorization = self.request.headers.get("AUTHORIZATION", None)

        if not authorization:
            return None

        token = authorization[4:]

        return self.get_user(token)

    @staticmethod
    def get_user(token):
        from apps.users.models import AccessToken
        try:
            access = AccessToken.objects.filter(token=token).last()
            if not access:
                return None
            user = access.user
            if not user.is_expired and user.last_active_on > (timezone.now() - datetime.timedelta(
                    days=settings.ACCESS_TOKEN_EXPIRY_LIMIT)):
                user.last_active_on = timezone.now()
                user.save()
                return user
            return None
        except AccessToken.DoesNotExist:
            return None


# class ChannelAuthentication:
#
#     def __init__(self, token):
#         self.token = token
#
#     def authentication(self):
#         data = self.validate_token()
#         if not data:
#             return None
#         return self.get_user()
#
#     def validate_token(self):
#         decoded = TokenManager.decode_token(self.token)
#         if not decoded:
#             return None
#         return decoded
#
#     @staticmethod
#     def get_user(self):
