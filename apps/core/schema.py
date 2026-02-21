import graphene

from apps.core.mutation import Mutation as appMutations
from apps.core.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass


class Mutation(
    appMutations,
    graphene.ObjectType
):
    pass
