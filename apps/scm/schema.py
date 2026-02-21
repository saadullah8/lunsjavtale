import graphene

from apps.scm.mutation import Mutation as appMutations
from apps.scm.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass


class Mutation(appMutations, graphene.ObjectType):
    pass
