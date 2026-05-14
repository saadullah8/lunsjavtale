import graphene
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphene_django.forms.types import DjangoFormInputObjectType
from graphql import GraphQLError

# local imports
from apps.bases.utils import (
    camel_case_format,
    get_object_by_id,
    raise_graphql_error,
    raise_graphql_error_with_fields,
)
from backend.permissions import is_admin_user, is_authenticated

from .forms import (
    AddressTypeForm,
    ContactUsForm,
    FAQCategoryForm,
    FAQForm,
    FollowUsForm,
    LanguageForm,
    PartnerForm,
    PromotionForm,
    SupportedBrandForm,
    ValidAreaForm,
    WhoUAreForm,
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


class ValidAreaMutation(DjangoModelFormMutation):
    """
        Admins can create and update Valid area information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ValidAreaType)

    class Meta:
        form_class = ValidAreaForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        form = ValidAreaForm(data=input)
        if form.data.get('id'):
            obj = get_object_by_id(ValidArea, form.data.get('id'))
            form = ValidAreaForm(data=input, instance=obj)
        if form.is_valid():
            obj, created = ValidArea.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return ValidAreaMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class ValidAreaDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = ValidArea.objects.get(id=id)
            obj.delete()
            return ValidAreaDelete(
                success=True,
                message="Successfully deleted",
            )
        except ValidArea.DoesNotExist:
            raise_graphql_error("Valid Area not found.", "valid_area_not_exist")


class ValidAreaBulkInput(graphene.InputObjectType):
    """Input for a single area in bulk import."""
    post_code = graphene.Int(required=True)
    name = graphene.String()


def _parse_areas_text(content):
    """Parse tab/space-separated text: one line per row, first column post_code, second name. Returns list of (post_code, name)."""
    import re
    seen = set()
    rows = []
    for line in (content or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[\t\s]+", line, maxsplit=1)
        if not parts:
            continue
        raw_code = parts[0].replace("\t", "").replace(" ", "")
        try:
            post_code = int(raw_code)
        except (ValueError, TypeError):
            continue
        if post_code < 0:
            continue
        if post_code in seen:
            continue
        seen.add(post_code)
        name = (parts[1].strip() if len(parts) > 1 else None) or None
        rows.append((post_code, name))
    return rows


class ValidAreaImportFromText(graphene.Mutation):
    """
    Admins import areas from raw file content (one line per row, tab/space separated: post_code, name).
    Avoids GraphQL variable list limits by sending a single string.
    """

    class Arguments:
        content = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    created_count = graphene.Int()
    updated_count = graphene.Int()
    error_count = graphene.Int()
    errors = graphene.List(graphene.String)

    @is_admin_user
    def mutate(self, info, content, **kwargs):
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        rows = _parse_areas_text(content or "")
        for post_code, name in rows:
            try:
                obj, created = ValidArea.objects.update_or_create(
                    post_code=post_code,
                    defaults={"name": name, "is_active": True},
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"Post code {post_code}: {str(e)}")
        return ValidAreaImportFromText(
            success=True,
            message=f"Import complete: {created_count} created, {updated_count} updated, {error_count} errors.",
            created_count=created_count,
            updated_count=updated_count,
            error_count=error_count,
            errors=errors if errors else None,
        )


class ValidAreaBulkImport(graphene.Mutation):
    """
    Admins can import many areas at once (e.g. from file).
    For each row: post_code (required), name (optional).
    Uses update_or_create on post_code so duplicates in the list or existing DB are handled.
    """

    class Arguments:
        areas = graphene.List(graphene.NonNull(ValidAreaBulkInput), required=True)

    success = graphene.Boolean()
    message = graphene.String()
    created_count = graphene.Int()
    updated_count = graphene.Int()
    error_count = graphene.Int()
    errors = graphene.List(graphene.String)

    @is_admin_user
    def mutate(self, info, areas, **kwargs):
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        for item in areas:
            post_code = item.get("post_code") or item.get("postCode")
            name = (item.get("name") or "").strip() or None
            if post_code is None:
                error_count += 1
                errors.append("Row missing post_code.")
                continue
            try:
                obj, created = ValidArea.objects.update_or_create(
                    post_code=post_code,
                    defaults={"name": name, "is_active": True},
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"Post code {post_code}: {str(e)}")

        return ValidAreaBulkImport(
            success=True,
            message=f"Import complete: {created_count} created, {updated_count} updated, {error_count} errors.",
            created_count=created_count,
            updated_count=updated_count,
            error_count=error_count,
            errors=errors if errors else None,
        )


class AddressTypeMutation(DjangoModelFormMutation):
    """
        Admins can create and update Address Type information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(TypeOfAddressType)

    class Meta:
        form_class = AddressTypeForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        form = AddressTypeForm(data=input)
        if form.data.get('id'):
            obj = get_object_by_id(TypeOfAddress, form.data.get('id'))
            form = AddressTypeForm(data=input, instance=obj)
        if form.is_valid():
            obj, created = TypeOfAddress.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return AddressTypeMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class AddressTypeDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = TypeOfAddress.objects.get(id=id)
            if obj.addresses.exists():
                raise_graphql_error("Already in use.")
            else:
                obj.delete()
            return AddressTypeDelete(
                success=True,
                message="Successfully deleted",
            )
        except TypeOfAddress.DoesNotExist:
            raise_graphql_error("Address Type not found.", "address_type_not_exist")


class LanguageMutation(DjangoModelFormMutation):
    """
        Admins can create and update Language information through a form input.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(LanguageType)

    class Meta:
        form_class = LanguageForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        form = LanguageForm(data=input)
        if form.data.get('id'):
            obj = get_object_by_id(Language, form.data.get('id'))
            form = LanguageForm(data=input, instance=obj)
        if form.is_valid():
            obj, created = Language.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return LanguageMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class LanguageDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = Language.objects.get(id=id)
            obj.delete()
            return LanguageDelete(
                success=True,
                message="Successfully deleted",
            )
        except Language.DoesNotExist:
            raise_graphql_error("Language not found.", "language_not_exist")


class FAQCategoryMutation(DjangoModelFormMutation):
    """
        update and create new FAQ Category information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(FAQCategoryType)

    class Meta:
        form_class = FAQCategoryForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = FAQCategoryForm(data=input)
        if form.data.get('id'):
            old_obj = get_object_by_id(FAQCategory, form.data['id'])
            form = FAQCategoryForm(data=input, instance=old_obj)
        if form.is_valid():
            obj, created = FAQCategory.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return FAQCategoryMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class FAQCategoryDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = FAQCategory.objects.get(id=id)
            obj.delete()
            return FAQCategoryDelete(
                success=True,
                message="Successfully deleted",
            )
        except FAQCategory.DoesNotExist:
            raise_graphql_error("FAQ Category not found.", "FAQ_category_not_exist")


class FAQMutation(DjangoModelFormMutation):
    """
        update and create new FAQ information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(FAQType)

    class Meta:
        form_class = FAQForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = FAQForm(data=input)
        if form.data.get('id'):
            old_obj = FAQ.objects.get(id=form.data['id'])
            form = FAQForm(data=input, instance=old_obj)
        if form.is_valid():
            obj, created = FAQ.objects.update_or_create(id=form.data.get('id'), defaults=form.cleaned_data)
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return FAQMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class FAQDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = FAQ.objects.get(id=id)
            obj.delete()
            return FAQDelete(
                success=True,
                message="Successfully deleted",
            )
        except FAQ.DoesNotExist:
            raise_graphql_error("FAQ not found.", "FAQ_not_exist")


class SupportedBrandMutation(DjangoModelFormMutation):
    """
        update and create new SupportedBrand information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(SupportedBrandType)

    class Meta:
        form_class = SupportedBrandForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = SupportedBrandForm(data=input, instance=SupportedBrand.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return SupportedBrandMutation(
            success=True, message="Successfully added", instance=obj
        )


class SupportedBrandDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = SupportedBrand.objects.get(id=id)
            obj.delete()
            return SupportedBrandDelete(
                success=True,
                message="Successfully deleted",
            )
        except SupportedBrand.DoesNotExist:
            raise_graphql_error("SupportedBrand not found.", "supported_brand_not_exist")


class PartnerMutation(DjangoModelFormMutation):
    """
        update and create new Partner information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(PartnerType)

    class Meta:
        form_class = PartnerForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = PartnerForm(data=input, instance=Partner.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return PartnerMutation(
            success=True, message="Successfully added", instance=obj
        )


class PartnerDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = Partner.objects.get(id=id)
            obj.delete()
            return PartnerDelete(
                success=True,
                message="Successfully deleted",
            )
        except Partner.DoesNotExist:
            raise_graphql_error("Partner not found.", "partner_not_exist")


class FollowUsMutation(DjangoModelFormMutation):
    """
        update and create new FollowUs information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(FollowUsType)

    class Meta:
        form_class = FollowUsForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = FollowUsForm(data=input, instance=FollowUs.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return FollowUsMutation(
            success=True, message="Successfully added", instance=obj
        )


class FollowUsDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = FollowUs.objects.get(id=id)
            obj.delete()
            return FollowUsDelete(
                success=True,
                message="Successfully deleted",
            )
        except FollowUs.DoesNotExist:
            raise_graphql_error("Follow Us not found.", "follow_us_not_exist")


class PromotionMutation(DjangoModelFormMutation):
    """
        update and create new Promotion information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(PromotionType)

    class Meta:
        form_class = PromotionForm

    def mutate_and_get_payload(self, info, **input):
        form = PromotionForm(data=input, instance=Promotion.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return PromotionMutation(
            success=True, message="Successfully added", instance=obj
        )


class PromotionDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = Promotion.objects.get(id=id)
            obj.delete()
            return PromotionDelete(
                success=True,
                message="Successfully deleted",
            )
        except Promotion.DoesNotExist:
            raise_graphql_error("Promotion not found.", "promotion_not_exist")


class ContactUsMutation(DjangoModelFormMutation):
    """
        update and create new ContactUs information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ContactUsType)

    class Meta:
        form_class = ContactUsForm

    def mutate_and_get_payload(self, info, **input):
        form = ContactUsForm(data=input, instance=ContactUs.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
            
            # Send Email to Admin
            from django.conf import settings
            from apps.users.tasks import send_email_on_delay
            
            subject = f"New Priority Desk Inquiry: {obj.category or 'General'}"
            context = {
                'name': obj.name,
                'email': obj.email,
                'company': obj.company_name,
                'phone': obj.contact,
                'category': obj.category,
                'message': obj.message,
                'year': 2026
            }
            template = 'emails/admin_contact_notification.html' # We'll create this or use a generic one
            
            # Sending to admin email defined in settings
            admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@lunsjavtale.no')
            send_email_on_delay.delay(template, context, subject, admin_email)
            
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return ContactUsMutation(
            success=True, message="Successfully sent. We will get back to you soon.", instance=obj
        )


class WhoUAreInputObjectType(DjangoFormInputObjectType):

    class Meta:
        form_class = WhoUAreForm


class WhoUAreAttachmentInput(graphene.InputObjectType):
    file_url = graphene.String()
    file_id = graphene.String()
    is_cover = graphene.Boolean()


class WhoUAreMutation(graphene.Mutation):
    """
        update and create new WhoUAre information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(WhoUAreType)

    class Arguments:
        input = WhoUAreInputObjectType()
        attachments = graphene.List(WhoUAreAttachmentInput)

    def mutate(self, info, input, attachments, **kwargs):
        form = WhoUAreForm(data=input, instance=WhoUAre.objects.filter(id=input.get('id')).last())
        if form.is_valid():
            obj = form.save()
            for attachment in attachments:
                WhoUAreAttachment.objects.create(
                    who_u_are=obj, file_url=attachment.get('file_url'), file_id=attachment.get('file_id'),
                    is_cover=attachment.get('is_cover')
                )
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise GraphQLError(
                message="Invalid input request.",
                extensions={
                    "errors": error_data,
                    "code": "invalid_input"
                }
            )
        return WhoUAreMutation(
            success=True, message="Successfully added", instance=obj
        )


class WhoUAreDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        try:
            obj = WhoUAre.objects.get(id=id)
            WhoUAreAttachment.objects.filter(who_u_are=obj).delete()
            obj.delete()
            return WhoUAreDelete(
                success=True,
                message="Successfully deleted",
            )
        except WhoUAre.DoesNotExist:
            raise_graphql_error("Who U Are not found.", "who_u_are_not_exist")


class Mutation(graphene.ObjectType):
    """
        define all the mutations by identifier name for query
    """
    valid_area_mutation = ValidAreaMutation.Field()
    valid_area_delete = ValidAreaDelete.Field()
    valid_area_bulk_import = ValidAreaBulkImport.Field()
    valid_area_import_from_text = ValidAreaImportFromText.Field()
    # address_type_mutation = AddressTypeMutation.Field()
    # address_type_delete = AddressTypeDelete.Field()
    language_mutation = LanguageMutation.Field()
    language_delete = LanguageDelete.Field()
    FAQ_category_mutation = FAQCategoryMutation.Field()
    FAQ_category_delete = FAQCategoryDelete.Field()
    FAQ_mutation = FAQMutation.Field()
    FAQ_delete = FAQDelete.Field()
    supported_brand_mutation = SupportedBrandMutation.Field()
    supported_brand_delete = SupportedBrandDelete.Field()
    partner_mutation = PartnerMutation.Field()
    partner_delete = PartnerDelete.Field()
    follow_us_mutation = FollowUsMutation.Field()
    follow_us_delete = FollowUsDelete.Field()
    promotion_mutation = PromotionMutation.Field()
    promotion_delete = PromotionDelete.Field()
    contact_us_mutation = ContactUsMutation.Field()
    who_u_are_mutation = WhoUAreMutation.Field()
    who_u_are_delete = WhoUAreDelete.Field()
