# third party imports

import graphene
from django.utils import timezone
from graphene_django.filter.fields import DjangoFilterConnectionField

# local imports
from apps.bases.utils import get_object_by_attrs, get_object_by_id
from backend.permissions import is_admin_user, is_authenticated

from .choices import AudienceTypeChoice
from .models import Notification, NotificationTemplate, NotificationViewer
from .object_types import NotificationTemplateType, NotificationType
from .tasks import make_seen_all_notifications


class NotificationQuery(graphene.ObjectType):
    """
        Define notification query.
        Notification type:: advertise, alert, chat, message, photo-verify, cv-verify.
        Audience type:: admins, users, seller, inactive-users, custom, single-user.
    """
    notification = graphene.Field(NotificationType, id=graphene.ID())
    admin_notifications = DjangoFilterConnectionField(NotificationType)
    unread_admin_notification_count = graphene.Int()
    notifications = DjangoFilterConnectionField(NotificationType)

    @is_admin_user
    def resolve_notification(self, info, id, **kwargs):
        notification = get_object_by_id(Notification, id)
        if info.context.user in notification.users.all():
            obj, created = NotificationViewer.objects.get_or_create(
                notification=notification,
                user=info.context.user
            )
            obj.view_count += 1
            obj.save()
        return notification

    @is_admin_user
    def resolve_admin_notifications(self, info, **kwargs):
        notifications = Notification.objects.filter(audience_type=AudienceTypeChoice.ADMINS)
        make_seen_all_notifications.delay(info.context.user.id)
        return notifications

    @is_admin_user
    def resolve_unread_admin_notification_count(self, info, **kwargs):
        notifications = Notification.objects.filter(audience_type=AudienceTypeChoice.ADMINS)
        qs = notifications
        read = NotificationViewer.objects.filter(notification__in=qs).values_list('notification', flat=True)
        return notifications.exclude(id__in=read).count()

    @is_admin_user
    def resolve_notifications(self, info, **kwargs):
        notifications = Notification.objects.all()
        return notifications


class NotificationTemplateQuery(graphene.ObjectType):
    """
        define notification template query
    """
    notification_template = graphene.Field(NotificationTemplateType, id=graphene.ID())
    all_notification_templates = DjangoFilterConnectionField(NotificationTemplateType)

    @is_admin_user
    def resolve_notification_template(self, info, id, **kwargs):
        notification_temp = get_object_by_id(NotificationTemplate, id)
        return notification_temp

    @is_admin_user
    def resolve_all_notification_templates(self, info, **kwargs):
        return NotificationTemplate.objects.all()


class Query(NotificationQuery, NotificationTemplateQuery):
    """
    """
    user_notification = graphene.Field(NotificationType, id=graphene.ID())
    user_notifications = DjangoFilterConnectionField(NotificationType)
    unread_notification_count = graphene.Int()

    @is_authenticated
    def resolve_user_notifications(self, info, **kwargs):
        user = info.context.user
        notifications = Notification.objects.filter(users=user, sent_on__lte=timezone.now())
        make_seen_all_notifications.delay(user.id)
        return notifications

    @is_authenticated
    def resolve_user_notification(self, info, id, **kwargs):
        user = info.context.user
        notification = get_object_by_attrs(
            Notification, {'id': id, 'users': user},
            {'name': 'id', 'value': id}
        )
        if notification and user in notification.users.all():
            obj, created = NotificationViewer.objects.get_or_create(
                notification=notification,
                user=user
            )
            obj.view_count = obj.view_count + 1
            obj.save()
        return notification

    @is_authenticated
    def resolve_unread_notification_count(self, info, **kwargs):
        user = info.context.user
        notifications = Notification.objects.filter(users=user, sent_on__lte=timezone.now())
        read = NotificationViewer.objects.filter(
            notification__in=notifications, user=user).values_list('notification', flat=True)
        return notifications.exclude(id__in=read).count()
