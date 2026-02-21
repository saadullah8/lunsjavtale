import graphene
from django.utils import timezone
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphene_django.forms.types import DjangoFormInputObjectType
from graphql import GraphQLError

# local imports
from apps.bases.utils import camel_case_format, get_object_by_id, raise_graphql_error
from apps.notifications.choices import NotificationTypeChoice
from apps.notifications.tasks import (
    send_admin_mail_for_vendor_product,
    send_admin_notification_and_save,
    send_notification_and_save,
    send_vendor_product_update_mail,
)
from backend.permissions import is_admin_user, is_authenticated, is_vendor_user

from ..sales.models import SellCart
from .choices import MeetingStatusChoices, ProductStatusChoices
from .forms import (
    CategoryForm,
    FoodMeetingForm,
    IngredientForm,
    ProductForm,
    VendorProductForm,
    WeeklyVariantForm,
)
from .models import (
    Category,
    FavoriteProduct,
    FoodMeeting,
    Ingredient,
    Product,
    ProductAttachment,
    WeeklyVariant,
)
from .object_types import (
    CategoryType,
    FoodMeetingType,
    IngredientType,
    ProductType,
    WeeklyVariantType,
)

USE_me = True


class CategoryMutation(DjangoModelFormMutation):
    """
        update and create new Category information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(CategoryType)

    class Meta:
        form_class = CategoryForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = CategoryForm(data=input)
        object_id = None
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(Category, object_id)
            form = CategoryForm(data=input, instance=old_obj)
        form_data = form.data
        if form.is_valid():
            obj, created = Category.objects.update_or_create(id=object_id, defaults=form_data)
            if obj.is_active:
                obj.products.update(discount_availability=True)
            else:
                obj.products.update(discount_availability=False)
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
        return CategoryMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class CategoryDeleteMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        with_all_product = graphene.Boolean()

    @is_admin_user
    def mutate(self, info, id, with_all_product=False, **kwargs):
        obj = Category.objects.get(id=id, is_deleted=False)
        if with_all_product:
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            obj.products.update(is_deleted=True, deleted_on=timezone.now())
            ProductAttachment.objects.filter(product__in=obj.products.all()).delete()
            SellCart.objects.filter(order__isnull=True, item__in=obj.products.all()).delete()
        else:
            obj.is_deleted = True
            obj.deleted_on = timezone.now()
            obj.save()
            obj.products.update(category=None)
        return CategoryDeleteMutation(
            success=True, message="Successfully deleted"
        )


class WeeklyVariantMutation(DjangoModelFormMutation):
    """
        update and create new WeeklyVariant information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(WeeklyVariantType)

    class Meta:
        form_class = WeeklyVariantForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = WeeklyVariantForm(data=input)
        object_id = None
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(WeeklyVariant, object_id)
            form = WeeklyVariantForm(data=input, instance=old_obj)
        form_data = form.data
        if form.is_valid():
            obj, created = WeeklyVariant.objects.update_or_create(id=object_id, defaults=form_data)
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
        return WeeklyVariantMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class IngredientMutation(DjangoModelFormMutation):
    """
        update and create new Ingredient information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(IngredientType)

    class Meta:
        form_class = IngredientForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        form = IngredientForm(data=input)
        object_id = None
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(Ingredient, object_id)
            form = IngredientForm(data=input, instance=old_obj)
        form_data = form.data
        if form.is_valid():
            obj, created = Ingredient.objects.update_or_create(id=object_id, defaults=form_data)
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
        return IngredientMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class IngredientDeleteMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        obj = Ingredient.objects.get(id=id, is_deleted=False)
        obj.is_deleted = True
        obj.deleted_on = timezone.now()
        obj.save()
        return IngredientDeleteMutation(
            success=True, message="Successfully deleted"
        )


class FoodMeetingMutation(DjangoModelFormMutation):
    """
        update and create new FoodMeeting information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(FoodMeetingType)

    class Meta:
        form_class = FoodMeetingForm

    # @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = FoodMeetingForm(data=input)
        if user and not user.is_admin:
            input['company'] = user.company.id
        if input.get('id') and user:
            if user.is_admin:
                form = FoodMeetingForm(data=input, instance=FoodMeeting.objects.get(id=input.get('id')))
            else:
                form = FoodMeetingForm(data=input, instance=FoodMeeting.objects.get(id=input.get('id'), company=user.company))
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
        return FoodMeetingMutation(
            success=True, message="Successfully added", instance=obj
        )


class FoodMeetingResolve(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        status = graphene.String()
        note = graphene.String()

    @is_admin_user
    def mutate(self, info, id, status, note, **kwargs):
        obj = FoodMeeting.objects.get(id=id)
        if status not in [MeetingStatusChoices.ATTENDED, MeetingStatusChoices.POSTPONED]:
            raise_graphql_error("Please select a valid choice.", field_name='status')
        obj.status = status
        obj.note = note
        obj.save()
        return FoodMeetingResolve(
            success=True, message="Succesfully resolved"
        )


class MeetingDeleteMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        obj = FoodMeeting.objects.get(id=id)
        obj.delete()
        return MeetingDeleteMutation(
            success=True, message="Successfully deleted"
        )


class ProductInput(DjangoFormInputObjectType):

    class Meta:
        form_class = ProductForm


class ProductAttachmentInput(graphene.InputObjectType):
    file_url = graphene.String()
    file_id = graphene.String()
    is_cover = graphene.Boolean()


class ProductMutation(graphene.Mutation):
    """
        update and create new Product information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        input = ProductInput(required=True)
        ingredients = graphene.List(graphene.String)
        attachments = graphene.List(ProductAttachmentInput, required=True)

    @is_admin_user
    def mutate(self, info, input, ingredients, attachments, **kwargs):
        form = ProductForm(data=input)
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(Product, object_id)
            form = ProductForm(data=input, instance=old_obj)
        if form.is_valid():
            obj = form.save()
            obj.ingredients.clear()
            for ing in ingredients:
                obj.ingredients.add(Ingredient.objects.get_or_create(name=ing)[0])
            obj.attachments.all().delete()
            for attach in attachments:
                ProductAttachment.objects.create(
                    product=obj, file_url=attach.get('file_url'), file_id=attach.get('file_id'),
                    is_cover=attach.get('is_cover')
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
        return ProductMutation(
            success=True, message=f"Successfully {'added' if input.get('id') else 'updated'}", instance=obj
        )


class VendorProductInput(DjangoFormInputObjectType):

    class Meta:
        form_class = VendorProductForm


class VendorProductMutation(graphene.Mutation):
    """
        update and create new Product information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        input = VendorProductInput()
        ingredients = graphene.List(graphene.String)
        attachments = graphene.List(ProductAttachmentInput)

    @is_vendor_user
    def mutate(self, info, input, ingredients, attachments=[], **kwargs):
        user = info.context.user
        form = ProductForm(data=input)
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(Product, object_id)
            form = ProductForm(data=input, instance=old_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.vendor = user.vendor
            obj.status = ProductStatusChoices.PENDING
            obj.save()
            obj.ingredients.clear()
            for ing in ingredients:
                obj.ingredients.add(Ingredient.objects.get_or_create(name=ing)[0])
            if attachments:
                obj.attachments.all().delete()
                for attach in attachments:
                    ProductAttachment.objects.create(
                        product=obj, file_url=attach.get('file_url'), file_id=attach.get('file_id'),
                        is_cover=attach.get('is_cover')
                    )
            send_admin_notification_and_save.delay(
                title="Vendor product update" if input.get('id') else "New vendor product",
                message=f"Vendor product updated by '{obj.vendor.name}'" if input.get('id') else f"New product added by '{obj.vendor.name}'",
                object_id=str(obj.id),
                n_type=NotificationTypeChoice.VENDOR_PRODUCT_ADDED
            )
            send_admin_mail_for_vendor_product.delay(
                obj.vendor.name, obj.name, input.get('id')
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
        return VendorProductMutation(
            success=True, message=f"Successfully {'added' if input.get('id') else 'updated'}", instance=obj
        )


class VerifyVendorProduct(graphene.Mutation):
    """
        While Verify vendor product Admin have to choose action
        like approve or reject. if reject have to
        reason of rejection.
        action::
            1. approved
            2. rejected
    """

    message = graphene.String()
    success = graphene.Boolean()
    instance = graphene.Field(ProductType)

    class Arguments:
        id = graphene.ID(required=True)
        status = graphene.String(required=True)
        note = graphene.String()

    @is_admin_user
    def mutate(self, info, id, status, note=""):
        if status not in [ProductStatusChoices.APPROVED, ProductStatusChoices.REJECTED]:
            raise_graphql_error("Please Choose between 'approved' or 'rejected'.", "invalid_action")
        try:
            obj = Product.objects.get(id=id)
            obj.status = status
            if status == ProductStatusChoices.APPROVED:
                obj.availability = True
            obj.note = note
            obj.save()
            send_notification_and_save.delay(
                user_id=obj.vendor.owner.id,
                title=f"Vendor product {status}",
                message=f"Your product '{obj.name}' is {status} by admins.",
                object_id=str(obj.vendor.id),
                n_type=NotificationTypeChoice.VENDOR_PRODUCT_UPDATED
            )
            send_vendor_product_update_mail.delay(
                obj.vendor.email, status, obj.name
            )
            return VerifyVendorProduct(
                instance=obj,
                success=True,
                message=f"Successfully {'verified' if status == ProductStatusChoices.APPROVED else 'rejected'}"
            )
        except Product.DoesNotExist:
            raise_graphql_error("Product not found.", "user_not_exist")


class ProductDeleteMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        obj = Product.objects.get(id=id, is_deleted=False)
        obj.is_deleted = True
        obj.deleted_on = timezone.now()
        obj.save()
        obj.attachments.all().delete()
        return ProductDeleteMutation(
            success=True, message="Successfully deleted"
        )


class FavoriteProductMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_authenticated
    def mutate(self, info, id, **kwargs):
        user = info.context.user
        obj = Product.objects.get(id=id)
        FavoriteProduct.objects.get_or_create(added_by=user, product=obj)
        return FavoriteProductMutation(
            success=True, message="Successfully added"
        )


class WeeklyVariantProductMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        products = graphene.List(graphene.ID)

    @is_admin_user
    def mutate(self, info, id, products, **kwargs):
        products = Product.objects.filter(id__in=products)
        obj = WeeklyVariant.objects.get(id=id)
        for p in products:
            p.weekly_variants.add(obj)
        for p in Product.objects.filter(weekly_variants=obj).exclude(id__in=products):
            p.weekly_variants.remove(obj)
        return WeeklyVariantProductMutation(
            success=True, message="Successfully added"
        )


class Mutation(graphene.ObjectType):
    """
        define all the mutations by identifier name for query
    """
    category_mutation = CategoryMutation.Field()
    category_delete = CategoryDeleteMutation.Field()
    weekly_variant_mutation = WeeklyVariantMutation.Field()
    ingredient_mutation = IngredientMutation.Field()
    ingredient_delete = IngredientDeleteMutation.Field()
    product_mutation = ProductMutation.Field()
    product_delete = ProductDeleteMutation.Field()
    vendor_product_mutation = VendorProductMutation.Field()
    verify_vendor_product = VerifyVendorProduct.Field()
    food_meeting_mutation = FoodMeetingMutation.Field()
    food_meeting_resolve = FoodMeetingResolve.Field()
    food_meeting_delete = MeetingDeleteMutation.Field()
    favorite_product_mutation = FavoriteProductMutation.Field()
    weekly_variant_products = WeeklyVariantProductMutation.Field()
