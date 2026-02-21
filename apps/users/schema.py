# at backend/users/schema.py
import graphene

from apps.users.mutation import Mutation as appMutations
from apps.users.query import Query as appQueries


class Query(appQueries, graphene.ObjectType):
    pass


class Mutation(appMutations, graphene.ObjectType):
    pass
