# third party imports

import graphene
from django.contrib.auth import get_user_model
from graphene_django.filter.fields import DjangoFilterConnectionField

from backend.permissions import is_authenticated

from .choices import MenuStatusChoices, MeetingTypeChoices, PricingTypeChoices, ProductTypeChoices
from .models import Category, FoodMeeting, Product, WeeklyVariant
from .object_types import (
    CategoryType,
    FoodMeetingType,
    Ingredient,
    IngredientType,
    ProductType,
    WeeklyVariantType,
)

# local imports

User = get_user_model()


def get_vendor_products(info, product_type=None):
    user = info.context.user
    qs = Product.queryset()
    if user and user.is_vendor:
        qs = qs.filter(vendor=user.vendor)
    if product_type:
        qs = qs.filter(product_type=product_type)
    return qs


class CategoryQuery(graphene.ObjectType):
    """
        query all category information
    """
    categories = DjangoFilterConnectionField(CategoryType)
    category = graphene.Field(CategoryType, id=graphene.ID())
    weekly_variants = DjangoFilterConnectionField(WeeklyVariantType)
    weekly_variant = graphene.Field(WeeklyVariantType, id=graphene.ID())

    def resolve_categories(self, info, **kwargs):
        return Category.queryset()

    def resolve_category(self, info, id, **kwargs):
        return Category.queryset().filter(id=id).last()

    def resolve_weekly_variants(self, info, **kwargs):
        return WeeklyVariant.objects.all()

    def resolve_weekly_variant(self, info, id, **kwargs):
        return WeeklyVariant.objects.all().filter(id=id).last()


class Query(CategoryQuery, graphene.ObjectType):
    """
        query all table information.
    """
    products = DjangoFilterConnectionField(ProductType, max_limit=None)
    product = graphene.Field(ProductType, id=graphene.ID())
    vendor_menus = DjangoFilterConnectionField(ProductType, max_limit=None)
    vendor_menu = graphene.Field(ProductType, id=graphene.ID())
    vendor_add_ons = DjangoFilterConnectionField(ProductType, max_limit=None)
    vendor_add_on = graphene.Field(ProductType, id=graphene.ID())
    ingredients = DjangoFilterConnectionField(IngredientType)
    ingredient = graphene.Field(IngredientType, id=graphene.ID())
    food_meetings = DjangoFilterConnectionField(FoodMeetingType)
    food_meeting = graphene.Field(FoodMeetingType, id=graphene.ID())
    meeting_type_choices = graphene.JSONString()
    product_type_choices = graphene.JSONString()
    menu_status_choices = graphene.JSONString()
    pricing_type_choices = graphene.JSONString()

    def resolve_products(self, info, **kwargs):
        return get_vendor_products(info).order_by('-average_rating', '-orders_count')

    def resolve_product(self, info, id, **kwargs):
        return get_vendor_products(info).filter(id=id).last()

    @is_authenticated
    def resolve_vendor_menus(self, info, **kwargs):
        return get_vendor_products(info, ProductTypeChoices.MENU)

    @is_authenticated
    def resolve_vendor_menu(self, info, id, **kwargs):
        return get_vendor_products(info, ProductTypeChoices.MENU).filter(id=id).last()

    @is_authenticated
    def resolve_vendor_add_ons(self, info, **kwargs):
        return get_vendor_products(info, ProductTypeChoices.ADD_ON)

    @is_authenticated
    def resolve_vendor_add_on(self, info, id, **kwargs):
        return get_vendor_products(info, ProductTypeChoices.ADD_ON).filter(id=id).last()

    def resolve_ingredients(self, info, **kwargs):
        user = info.context.user
        if user and user.is_admin:
            qs = Ingredient.objects.all()
        else:
            qs = Ingredient.queryset()
        return qs

    def resolve_ingredient(self, info, id, **kwargs):
        user = info.context.user
        if user and user.is_admin:
            qs = Ingredient.objects.filter(id=id)
        else:
            qs = Ingredient.queryset().filter(id=id)
        return qs.last()

    @is_authenticated
    def resolve_food_meetings(self, info, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = FoodMeeting.objects.all()
        else:
            qs = FoodMeeting.objects.filter(company=user.company)
        return qs

    @is_authenticated
    def resolve_food_meeting(self, info, id, **kwargs):
        user = info.context.user
        if user.is_admin:
            qs = FoodMeeting.objects.filter(id=id)
        else:
            qs = FoodMeeting.objects.filter(company=user.company, id=id)
        return qs.last()

    def resolve_meeting_type_choices(self, info, **kwargs):
        return [{'key': c[0], 'display': c[1]} for c in MeetingTypeChoices.choices]

    def resolve_product_type_choices(self, info, **kwargs):
        return [{'key': c[0], 'display': c[1]} for c in ProductTypeChoices.choices]

    def resolve_menu_status_choices(self, info, **kwargs):
        return [{'key': c[0], 'display': c[1]} for c in MenuStatusChoices.choices]

    def resolve_pricing_type_choices(self, info, **kwargs):
        return [{'key': c[0], 'display': c[1]} for c in PricingTypeChoices.choices]
