
import graphene
from graphene_django import DjangoObjectType

# local imports
from backend.count_connection import CountConnection

from .filters import (
    ContactUsFilters,
    FAQCategoryFilters,
    FAQFilters,
    FollowUsFilters,
    LanguageFilter,
    PartnerFilters,
    PromotionFilters,
    SupportedBrandFilters,
    TypeOfAddressFilter,
    ValidAreaFilters,
    WhoUAreAttachmentFilters,
    WhoUAreFilters,
)
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
    WhoUAreAttachment,
)


class TypeOfAddressType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = TypeOfAddress
        filterset_class = TypeOfAddressFilter
        interfaces = (graphene.relay.Node, )
        convert_choices_to_enum = False
        connection_class = CountConnection


class LanguageType(DjangoObjectType):
    id = graphene.ID(required=True)

    class Meta:
        model = Language
        filterset_class = LanguageFilter
        interfaces = (graphene.relay.Node, )
        convert_choices_to_enum = False
        connection_class = CountConnection


class FAQCategoryType(DjangoObjectType):
    """
        define django object type for FAQ Category model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = FAQCategory
        filterset_class = FAQCategoryFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class FAQType(DjangoObjectType):
    """
        define django object type for FAQ model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = FAQ
        filterset_class = FAQFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class ValidAreaType(DjangoObjectType):
    """
        define django object type for valid area model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = ValidArea
        filterset_class = ValidAreaFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class SupportedBrandType(DjangoObjectType):
    """
        define django object type for Supported Brand model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = SupportedBrand
        filterset_class = SupportedBrandFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class PartnerType(DjangoObjectType):
    """
        define django object type for Partner model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = Partner
        filterset_class = PartnerFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class FollowUsType(DjangoObjectType):
    """
        define django object type for FollowUs model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = FollowUs
        filterset_class = FollowUsFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class PromotionType(DjangoObjectType):
    """
        define django object type for Promotion model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = Promotion
        filterset_class = PromotionFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class WhoUAreType(DjangoObjectType):
    """
        define django object type for WhoUAre model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = WhoUAre
        filterset_class = WhoUAreFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class WhoUAreAttachmentType(DjangoObjectType):
    """
        define django object type for WhoUAreAttachment model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = WhoUAreAttachment
        exclude = ['who_u_are']
        filterset_class = WhoUAreAttachmentFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection


class ContactUsType(DjangoObjectType):
    """
        define django object type for WhoUAreAttachment model with filter-set
    """
    id = graphene.ID(required=True)

    class Meta:
        model = ContactUs
        filterset_class = ContactUsFilters
        interfaces = (graphene.relay.Node,)
        convert_choices_to_enum = False
        connection_class = CountConnection
