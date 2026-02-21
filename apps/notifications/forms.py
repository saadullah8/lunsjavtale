from django import forms
from django.contrib.auth import get_user_model

from .models import Notification, NotificationTemplate

User = get_user_model()


class NotificationForm(forms.ModelForm):
    scheduled_on = forms.DateTimeField(required=False)
    users = forms.ModelMultipleChoiceField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Notification
        exclude = ('sent_on', 'object_id', 'user', 'notification_type')


class NotificationTemplateForm(forms.ModelForm):

    class Meta:
        model = NotificationTemplate
        exclude = '__all__'
