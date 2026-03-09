
import graphene
from graphene_django.debug import DjangoDebug

import apps.analytics.schema as analytics_schema
import apps.core.schema as core_schema
import apps.core.object_types as core_object_types
import apps.core.models as core_models
import apps.notifications.schema as notifications_schema
import apps.sales.schema as sales_schema
import apps.scm.schema as scm_schema
import apps.users.schema as user_schema


class Query(
    core_schema.Query,
    sales_schema.Query,
    scm_schema.Query,
    user_schema.Query,
    analytics_schema.Query,
    notifications_schema.Query,
    graphene.ObjectType
):
    """All query will in include this class"""
    debug = graphene.Field(DjangoDebug, name='_debug')
    validAreasSearch = graphene.List(
        core_object_types.ValidAreaType,
        term=graphene.String(),
        first=graphene.Int(),
    )

    def resolve_validAreasSearch(self, info, term=None, first=None, **kwargs):
        qs = core_models.ValidArea.objects.all().order_by('name', 'post_code')
        if term is not None and str(term).strip():
            qs = qs.filter(name__icontains=str(term).strip())
        limit = 100 if first is None else max(1, min(int(first), 500))
        return list(qs[:limit])


class Mutation(
    core_schema.Mutation,
    sales_schema.Mutation,
    scm_schema.Mutation,
    user_schema.Mutation,
    notifications_schema.Mutation,
    graphene.ObjectType
):
    """All mutation will in include this class"""
    pass


schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
)
