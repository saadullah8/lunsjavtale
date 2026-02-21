import graphene

from apps.analytics.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass
