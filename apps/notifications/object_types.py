# third party imports

import graphene
from graphene_django import DjangoObjectType

# local imports
from backend.count_connection import CountConnection

from .filters import NotificationFilter, NotificationTemplateFilter
from .models import Notification, NotificationTemplate, NotificationViewer


class NotificationType(DjangoObjectType):
    """
    """
    id = graphene.ID(required=True)
    status = graphene.String()
    is_seen = graphene.Boolean()

    class Meta:
        model = Notification
        filterset_class = NotificationFilter
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_status(self, info, **kwargs):
        return self.notification_status

    @staticmethod
    def resolve_is_seen(self, info, **kwargs):
        return self.is_seen


class NotificationTemplateType(DjangoObjectType):
    """
        defining django object type for notification template model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = NotificationTemplate
        filterset_class = NotificationTemplateFilter
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class NotificationViewerType(DjangoObjectType):
    """
        defining django object type for notification viewer model with filter-set
    """

    class Meta:
        model = NotificationViewer
        convert_choices_to_enum = False
