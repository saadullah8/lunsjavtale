
# third party imports
import graphene
from graphene_django import DjangoObjectType

# local imports
from apps.scm.filters import (
    CategoryFilters,
    FavoriteProductFilters,
    FoodMeetingFilters,
    IngredientFilters,
    ProductAttachmentFilters,
    ProductFilters,
    WeeklyVariantFilters,
)
from backend.count_connection import CountConnection

from .models import (
    Category,
    FavoriteProduct,
    FoodMeeting,
    Ingredient,
    Product,
    ProductAttachment,
    WeeklyVariant,
)


class CategoryType(DjangoObjectType):
    """
        define django object type for category model with category filter-set
    """
    id = graphene.ID(required=True)
    products_added = graphene.Int()

    class Meta:
        model = Category
        filterset_class = CategoryFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_products_added(self, info):
        return self.products.count()


class WeeklyVariantType(DjangoObjectType):
    """
        define django object type for WeeklyVariant model with category filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = WeeklyVariant
        filterset_class = WeeklyVariantFilters
        exclude = ['is_deleted', 'deleted_on']
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class ProductType(DjangoObjectType):
    """
        define django object type for product model with product filter-set
    """
    id = graphene.ID(required=True)
    is_favorite = graphene.Boolean()

    class Meta:
        model = Product
        filterset_class = ProductFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_is_favorite(self, info, **kwargs):
        return self.favorites.filter(added_by=info.context.user).exists()


class IngredientType(DjangoObjectType):
    """
        define django object type for Ingredient model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = Ingredient
        filterset_class = IngredientFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class ProductAttachmentType(DjangoObjectType):
    """
        define django object type for ProductAttachment model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = ProductAttachment
        filterset_class = ProductAttachmentFilters
        exclude = ['product']
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class FoodMeetingType(DjangoObjectType):
    """
        define django object type for FoodMeeting model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = FoodMeeting
        filterset_class = FoodMeetingFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class FavoriteProductType(DjangoObjectType):
    """
        define django object type for FavoriteProduct model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = FavoriteProduct
        filterset_class = FavoriteProductFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection
