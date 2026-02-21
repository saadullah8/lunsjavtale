from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from ..bases.models import BaseWithoutID

# local imports
from .choices import AudienceTypeChoice

User = get_user_model()


class Notification(BaseWithoutID):
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True
    )  # user responsible for notification
    users = models.ManyToManyField(
        User, blank=True, related_name="notified_users"
    )  # multiple users for notifications
    audience_type = models.CharField(
        max_length=32, choices=AudienceTypeChoice.choices
    )  # for whom the notification was created
    notification_type = models.CharField(max_length=32)  # what type of notification was sent
    title = models.CharField(max_length=128)  # subject of the notification
    message = models.TextField()  # body of the notification
    scheduled_on = models.DateTimeField(default=timezone.now)  # set time of send notification
    sent_on = models.DateTimeField(blank=True, null=True)  # notification sending time
    object_id = models.CharField(max_length=64, blank=True, null=True)  # store id of respective section

    class Meta:
        db_table = f"{settings.DB_PREFIX}_notifications"  # define table name for database
        ordering = ['-created_on']  # define default order as created in descending

    @property
    def notification_status(self):
        if self.sent_on:
            return 'sent'
        elif self.scheduled_on < timezone.now() and not self.sent_on:
            return "not-sent"
        return 'pending'

    @property
    def is_seen(self):
        qs = NotificationViewer.objects.filter(
            notification=self
        )
        if self.audience_type != AudienceTypeChoice.ADMINS:
            qs = qs.filter(user__in=self.users.all())
        if qs.exists():
            return True
        return False

    def __str__(self):
        return f"{self.pk}. {self.audience_type}/{self.notification_type}: {self.title}"


class NotificationTemplate(BaseWithoutID):
    title = models.CharField(max_length=64)  # title of the template
    message = models.TextField()  # body of the template

    class Meta:
        db_table = f"{settings.DB_PREFIX}_notification_templates"  # define table name for database
        ordering = ['-id']  # define default order as id in descending

    def __str__(self):
        return f"{self.title}:: {self.message}"


class NotificationViewer(BaseWithoutID):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)  # related to which notification
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='user_notifications_viewed')  # who checked the notification
    view_count = models.PositiveIntegerField(
        default=0)  # check how many times notification seen

    class Meta:
        db_table = f"{settings.DB_PREFIX}_notification_viewers"  # define table name for database
        ordering = ['-id']  # define default order as id in descending
