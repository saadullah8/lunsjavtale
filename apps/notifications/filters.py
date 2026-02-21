# third party imports
import django_filters

# local imports
from apps.bases.filters import BaseFilterOrderBy

from .models import Notification


class NotificationFilter(BaseFilterOrderBy):
    """
        Defining filtering for notifications.
    """
    title = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains'
    )
    audience_type = django_filters.CharFilter(
        field_name='audience_type', lookup_expr='icontains'
    )
    notification_type = django_filters.CharFilter(
        field_name='notification_type', lookup_expr='icontains'
    )
    user = django_filters.CharFilter(
        field_name='user__id', lookup_expr='icontains'
    )
    created_on = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='exact'
    )
    updated_on = django_filters.CharFilter(
        field_name='updated_on__date', lookup_expr='exact'
    )
    start = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='gte'
    )
    end = django_filters.CharFilter(
        field_name='created_on__date', lookup_expr='lte'
    )

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'audience_type',
            'notification_type',
            'user',
            'created_on',
            'updated_on'
        ]


class NotificationTemplateFilter(BaseFilterOrderBy):
    """
        Defining filtering for notification templates
    """
    title = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains'
    )
    message = django_filters.CharFilter(
        field_name='message', lookup_expr='icontains'
    )

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'message'
        ]
