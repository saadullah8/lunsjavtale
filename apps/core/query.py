
import graphene
from django.contrib.auth import get_user_model
from graphene_django.filter.fields import DjangoFilterConnectionField

from .models import (
    FAQ,
    ContactUs,
    FAQCategory,
    FollowUs,
    Language,
    Partner,
    Promotion,
    SupportedBrand,
    TypeOfAddress,
    ValidArea,
    WhoUAre,
)
from .object_types import (
    ContactUsType,
    FAQCategoryType,
    FAQType,
    FollowUsType,
    LanguageType,
    PartnerType,
    PromotionType,
    SupportedBrandType,
    TypeOfAddressType,
    ValidAreaType,
    WhoUAreType,
)

User = get_user_model()


class Query(graphene.ObjectType):
    """
        define all queries together
    """
    languages = DjangoFilterConnectionField(LanguageType)
    language = graphene.Field(LanguageType, id=graphene.ID())
    FAQ_categories = DjangoFilterConnectionField(FAQCategoryType)
    FAQ_category = graphene.Field(FAQCategoryType, id=graphene.ID())
    FAQ_list = DjangoFilterConnectionField(FAQType, max_limit=None)
    FAQ_object = graphene.Field(FAQType, id=graphene.ID())
    address_types = DjangoFilterConnectionField(TypeOfAddressType)
    address_type = graphene.Field(TypeOfAddressType, id=graphene.ID())
    valid_areas = DjangoFilterConnectionField(ValidAreaType)
    valid_area = graphene.Field(ValidAreaType, id=graphene.ID())
    supported_brands = DjangoFilterConnectionField(SupportedBrandType)
    supported_brand = graphene.Field(SupportedBrandType, id=graphene.ID())
    partners = DjangoFilterConnectionField(PartnerType)
    partner = graphene.Field(PartnerType, id=graphene.ID())
    follow_us_list = DjangoFilterConnectionField(FollowUsType)
    follow_us_object = graphene.Field(FollowUsType, id=graphene.ID())
    who_u_are_list = DjangoFilterConnectionField(WhoUAreType)
    who_u_are_object = graphene.Field(WhoUAreType, id=graphene.ID())
    contact_us_list = DjangoFilterConnectionField(ContactUsType)
    check_post_code = graphene.Boolean(post_code=graphene.Int())
    promotions = DjangoFilterConnectionField(PromotionType)
    promotion = graphene.Field(PromotionType, id=graphene.ID())

    def resolve_address_types(self, info, **kwargs):
        user = info.context.user
        if user and user.is_admin:
            return TypeOfAddress.objects.all()
        return TypeOfAddress.objects.filter(is_active=True)

    def resolve_address_type(self, info, id, **kwargs):
        user = info.context.user
        if user and user.is_admin:
            return TypeOfAddress.objects.filter(id=id).last()
        return TypeOfAddress.objects.filter(id=id, is_active=True).last()

    def resolve_languages(self, info, **kwargs):
        return Language.objects.all()

    def resolve_language(self, info, id, **kwargs):
        return Language.objects.filter(id=id).last()

    def resolve_FAQ_categories(self, info, **kwargs):
        return FAQCategory.objects.all()

    def resolve_FAQ_category(self, info, id, **kwargs):
        return FAQCategory.objects.filter(id=id).last()

    def resolve_FAQ_list(self, info, **kwargs):
        # FAQ.objects.update(view_count=F('view_count') + 1)
        return FAQ.objects.all()

    def resolve_FAQ_object(self, info, id, **kwargs):
        obj = FAQ.objects.filter(id=id).last()
        # if obj:
        #     obj.view_count = obj.view_count + 1
        #     obj.save()
        return obj

    def resolve_valid_areas(self, info, **kwargs):
        return ValidArea.objects.all()

    def resolve_valid_area(self, info, id, **kwargs):
        obj = ValidArea.objects.filter(id=id).last()
        return obj

    def resolve_check_post_code(self, info, post_code, **kwargs):
        return ValidArea.objects.filter(post_code=post_code, is_active=True).exists()

    def resolve_supported_brands(self, info, **kwargs):
        return SupportedBrand.objects.all()

    def resolve_supported_brand(self, info, id, **kwargs):
        obj = SupportedBrand.objects.filter(id=id).last()
        return obj

    def resolve_partners(self, info, **kwargs):
        return Partner.objects.all()

    def resolve_partner(self, info, id, **kwargs):
        obj = Partner.objects.filter(id=id).last()
        return obj

    def resolve_follow_us_list(self, info, **kwargs):
        return FollowUs.objects.all()

    def resolve_follow_us_object(self, info, id, **kwargs):
        obj = FollowUs.objects.filter(id=id).last()
        return obj

    def resolve_who_u_are_list(self, info, **kwargs):
        return WhoUAre.objects.all()

    def resolve_who_u_are_object(self, info, id, **kwargs):
        obj = WhoUAre.objects.filter(id=id).last()
        return obj

    def resolve_promotions(self, info, **kwargs):
        user = info.context.user
        if user and user.is_admin:
            return Promotion.objects.all()
        return Promotion.objects.filter(is_active=True)

    def resolve_promotion(self, info, id, **kwargs):
        return Promotion.objects.filter(id=id).last()

    def resolve_contact_us_list(self, info, **kwargs):
        return ContactUs.objects.all()
