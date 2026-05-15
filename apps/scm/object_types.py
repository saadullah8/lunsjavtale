
# third party imports
import graphene
from graphene_django import DjangoObjectType
from graphene.types.generic import GenericScalar

# local imports
from apps.scm.filters import (
    CategoryFilters,
    FavoriteProductFilters,
    FoodMeetingFilters,
    IngredientFilters,
    MenuItemFilters,
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
    MenuItem,
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
    vendor_products = graphene.List(lambda: ProductType, vendor_id=graphene.ID(), title=graphene.String())

    class Meta:
        model = Category
        filterset_class = CategoryFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    @staticmethod
    def resolve_products_added(self, info):
        return self.products.count()

    def resolve_vendor_products(self, info, vendor_id=None, title=None):
        qs = self.products.filter(is_deleted=False)
        if vendor_id:
            from apps.users.models import Vendor
            # Manual decode if it looks like a Relay ID (Base64)
            pk = vendor_id
            if not str(vendor_id).isdigit():
                try:
                    import base64
                    decoded = base64.b64decode(vendor_id).decode()
                    if ':' in decoded:
                        pk = decoded.split(':')[-1]
                except Exception:
                    pass
            qs = qs.filter(vendor_id=pk)
        
        if title:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=title) | Q(description__icontains=title))
            
        return qs.order_by('order')


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
    contains = GenericScalar()
    available_days = GenericScalar()
    blackout_dates = GenericScalar()
    dietary_tags = GenericScalar()
    delivery_fee = graphene.Decimal()
    delivery_time = graphene.String()
    # Adding camelCase names explicitly to ensure GraphiQL picks them up correctly
    average_rating = graphene.Decimal(source='average_rating')
    orders_count = graphene.Int(source='orders_count')
    badge = graphene.String(source='badge')
    is_popular = graphene.Boolean(source='is_popular')
    is_featured = graphene.Boolean(source='is_featured')

    class Meta:
        model = Product
        filterset_class = ProductFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection

    def resolve_is_favorite(self, info, **kwargs):
        user = info.context.user
        if user.is_authenticated:
            return self.favorites.filter(added_by=user).exists()
        return False

    def resolve_delivery_fee(self, info):
        from decimal import Decimal
        if self.vendor and hasattr(self.vendor, 'delivery_settings'):
            return self.vendor.delivery_settings.base_delivery_fee
        return Decimal("0.00")

    def resolve_delivery_time(self, info):
        if self.vendor and hasattr(self.vendor, 'delivery_settings'):
            settings = self.vendor.delivery_settings
            return f"{settings.min_delivery_time}-{settings.max_delivery_time} minutes"
        return "15-30 minutes"


class MenuItemType(DjangoObjectType):
    """
        define django object type for package menu items
    """
    id = graphene.ID(required=True)
    allergens = GenericScalar()

    class Meta:
        model = MenuItem
        filterset_class = MenuItemFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


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
