# third party imports
import datetime
from logging import getLogger

import graphene
from django.utils import timezone
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql import GraphQLError

# local imports
from apps.bases.utils import camel_case_format, get_object_by_id, raise_graphql_error
from apps.users.models import User, UserDeviceToken
from backend.permissions import is_admin_user

from .choices import AudienceTypeChoice, NotificationTypeChoice
from .forms import NotificationForm, NotificationTemplateForm
from .models import Notification, NotificationTemplate
from .object_types import NotificationTemplateType, NotificationType
from .tasks import send_user_bulk_notification


class NotificationMutation(DjangoModelFormMutation):
    """
        define graphene mutation for notification model.
        pass id in input fields for updating object
        for 'custom' as audience_type need to pass user-email list.
        audience_type::
        1. users
        3. inactive-users
        4. custom
    """
    success = graphene.Boolean()
    message = graphene.String()
    notification = graphene.Field(NotificationType)

    class Meta:
        form_class = NotificationForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = NotificationForm(data=input)
        object_id = None
        if form.data.get('id'):
            instance = get_object_by_id(Notification, form.data['id'])
            form = NotificationForm(data=input, instance=instance)
            object_id = instance.id
        users = None
        if form.data['audience_type'] == AudienceTypeChoice.USERS:
            users = User.objects.filter(is_staff=False, is_superuser=False, is_active=True)
        elif form.data['audience_type'] == AudienceTypeChoice.INACTIVE_USERS:
            users = User.objects.filter(is_staff=False, is_superuser=False, is_active=False)
        # elif form.data['audience_type'] == AudienceTypeChoice.SELLER:
        #     users = list(set(list(BaseAdvertise.objects.values_list('user__email').distinct())))
            users = User.objects.filter(is_active=True, email__in=[user[0] for user in users])
        elif form.data['audience_type'] == AudienceTypeChoice.CUSTOM:
            if not form.data.get('users'):
                raise GraphQLError(
                    message="Invalid input request.",
                    extensions={
                        "errors": {"users": "User list required for custom audience type."},
                        "code": "invalid_input"
                    }
                )
            users = User.objects.filter(is_active=True, id__in=form.data.get('users'))
        else:
            raise_graphql_error("Please select valid audience-type.")
        if form.is_valid():
            form.cleaned_data['notification_type'] = NotificationTypeChoice.ALERT
            if not form.cleaned_data.get('id'):
                form.cleaned_data['user'] = info.context.user
            del form.cleaned_data['users']
            if not form.data.get('scheduled_on'):
                del form.cleaned_data['scheduled_on']
            obj, created = Notification.objects.update_or_create(id=object_id, defaults=form.cleaned_data)
            obj.users.clear()
            obj.users.add(*users)
            # if obj.scheduled_on.replace(second=0, microsecond=0) == timezone.now().replace(second=0, microsecond=0):
            if (timezone.now() - datetime.timedelta(seconds=60)) <= obj.scheduled_on <= timezone.now():
                obj.sent_on = obj.scheduled_on
                obj.save()
                tokens = UserDeviceToken.objects.filter(user__in=obj.users.all())
                tokens = list(set(tokens.values_list('device_token', flat=True).distinct()))
                if tokens:
                    send_user_bulk_notification.delay(obj.title, obj.message, tokens, obj.notification_type)
                else:
                    getLogger().error("No user device tokens found.")
            elif obj.scheduled_on.replace(second=0, microsecond=0) > timezone.now().replace(second=0, microsecond=0):
                obj.sent_on = None
                obj.save()
            else:
                if created:
                    obj.sent_on = timezone.now()
                    tokens = UserDeviceToken.objects.filter(user__in=obj.users.all())
                    tokens = list(set(tokens.values_list('device_token', flat=True).distinct()))
                    if tokens:
                        send_user_bulk_notification.delay(obj.title, obj.message, tokens, obj.notification_type)
                    else:
                        getLogger().error("No user device tokens found.")
                else:
                    obj.sent_on = obj.scheduled_on
                obj.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return NotificationMutation(
            success=True, notification=obj,
            message=f"Successfully {'updated' if input.get('id') else 'added' }")


class NotificationTemplateMutation(DjangoModelFormMutation):
    """
        define graphene mutation for notification template model.
    """
    success = graphene.Boolean()
    message = graphene.String()
    object = graphene.Field(NotificationTemplateType)

    class Meta:
        form_class = NotificationTemplateForm

    @is_admin_user
    def mutate_and_get_payload(selft, info, **input):
        form = NotificationTemplateForm(data=input)
        if form.data.get('id'):
            obj = get_object_by_id(NotificationTemplate, form.data['id'])
            form = NotificationTemplateForm(data=input, instance=obj)
        if form.is_valid():
            obj, created = NotificationTemplate.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return NotificationTemplateMutation(
            success=True,
            object=obj,
            message=f"Successfully {'updated' if not created else 'added' }"
        )


class NotificationTemplateDeleteMutation(graphene.Mutation):
    """
        define graphene mutation for delete notification template.
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        obj = get_object_by_id(NotificationTemplate, id)
        # obj = NotificationTemplate.objects.get(id=id)
        obj.delete()
        return NotificationTemplateDeleteMutation(
            success=True,
            message="Notification template was deleted successfully."
        )


class NotificationDeleteMutation(graphene.Mutation):
    """
        define graphene mutation for delete notification template.
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        ids = graphene.List(graphene.ID, required=False)

    @is_admin_user
    def mutate(self, info, ids, **kwargs):
        user = info.context.user
        if user.is_admin:
            notifications = Notification.objects.filter(audience_type=AudienceTypeChoice.ADMINS)
        else:
            notifications = Notification.objects.filter(users=user)
        if ids:
            notifications = notifications.filter(id__in=ids)
        notifications.delete()
        return NotificationDeleteMutation(
            success=True,
            message="Notification was deleted successfully."
        )


class Mutation(graphene.ObjectType):
    """
        define all mutations through names to call
    """
    notification_mutation = NotificationMutation.Field()
    notification_template_mutation = NotificationTemplateMutation.Field()
    notification_template_delete = NotificationTemplateDeleteMutation.Field()
    notification_delete = NotificationDeleteMutation.Field()
