import graphene

from apps.sales.mutation import Mutation as appMutations
from apps.sales.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass


class Mutation(appMutations, graphene.ObjectType):
    pass
