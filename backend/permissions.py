from graphql import GraphQLError

from apps.users.choices import RoleTypeChoices


def is_authenticated(func):
    def wrapper(cls, info, **kwargs):
        if not info.context.user:
            raise GraphQLError(
                message='You are not authorized user.',
                extensions={
                    "message": "You are not authorized user.",
                    "code": "unauthorised"
                })
        return func(cls, info, **kwargs)
    return wrapper


def is_company_user(func):
    def wrapper(cls, info, **kwargs):
        user = info.context.user
        if not user or not user.company or user.role not in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER]:
            raise GraphQLError(
                message='You are not authorized user.',
                extensions={
                    "message": "You are not authorized user.",
                    "code": "unauthorised"
                })
        return func(cls, info, **kwargs)
    return wrapper


def is_vendor_user(func):
    def wrapper(cls, info, **kwargs):
        user = info.context.user
        if not user or not user.is_vendor:
            raise GraphQLError(
                message='You are not authorized user.',
                extensions={
                    "message": "You are not authorized user.",
                    "code": "unauthorised"
                })
        return func(cls, info, **kwargs)
    return wrapper


def is_super_admin(func):
    def wrapper(cls, info, **kwargs):
        if not info.context.user:
            raise GraphQLError(
                message='You are not authorized user.',
                extensions={
                    "message": "You are not authorized user.",
                    "code": "unauthorised"
                })
        elif not info.context.user.is_superuser:
            raise GraphQLError(
                message='You are not authorized to perform this operation.',
                extensions={
                    "message": "You are not authorized to perform this operation.",
                    "code": "unauthorised"
                })
        return func(cls, info, **kwargs)
    return wrapper


def is_admin_user(func):
    def wrapper(cls, info, **kwargs):
        if not info.context.user:
            raise GraphQLError(
                message="Unauthorized user!",
                extensions={
                    "error": "You are not authorized user.",
                    "code": "unauthorized"
                }
            )
        if not info.context.user.is_admin:
            raise GraphQLError(
                message="User is not permitted.",
                extensions={
                    "error": "You are not authorized to perform operations.",
                    "code": "invalid_permission"
                }
            )
        return func(cls, info, **kwargs)

    return wrapper
