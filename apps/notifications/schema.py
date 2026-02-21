
import graphene

from apps.notifications.mutation import Mutation as appMutations
from apps.notifications.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass


class Mutation(appMutations, graphene.ObjectType):
    pass
