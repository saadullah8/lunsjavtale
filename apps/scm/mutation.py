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
from .choices import MenuStatusChoices, MeetingStatusChoices, PricingTypeChoices, ProductStatusChoices, ProductTypeChoices
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
    MenuItem,
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


class MenuItemInput(graphene.InputObjectType):
    id = graphene.ID()
    title = graphene.String(required=True)
    allergens = graphene.List(graphene.String)
    image_url = graphene.String()
    file_id = graphene.String()
    order = graphene.Int()


class VendorMenuInput(graphene.InputObjectType):
    id = graphene.ID()
    name = graphene.String(required=True)
    title = graphene.String()
    description = graphene.String(required=True)
    category = graphene.ID()
    menu_type = graphene.String()
    price_with_tax = graphene.Decimal(required=True)
    tax_percent = graphene.Decimal()
    pricing_type = graphene.String()
    minimum_guests = graphene.Int()
    menu_status = graphene.String()
    min_lead_time_hours = graphene.Int()
    available_days = graphene.List(graphene.String)
    blackout_dates = graphene.List(graphene.String)
    dietary_tags = graphene.List(graphene.String)
    custom_dietary = graphene.String()
    contains = graphene.JSONString()
    is_adjustable_for_single_staff = graphene.Boolean()


class VendorAddOnInput(graphene.InputObjectType):
    id = graphene.ID()
    name = graphene.String(required=True)
    title = graphene.String()
    description = graphene.String()
    category = graphene.ID()
    price_with_tax = graphene.Decimal(required=True)
    tax_percent = graphene.Decimal()
    menu_status = graphene.String()
    dietary_tags = graphene.List(graphene.String)
    custom_dietary = graphene.String()
    contains = graphene.JSONString()


def validate_choice(value, choices, field_name):
    if value and value not in choices:
        raise_graphql_error("Please select a valid choice.", field_name=field_name)
    return value


def get_vendor_product(user, product_id, product_type=None):
    qs = Product.objects.filter(id=product_id, vendor=user.vendor, is_deleted=False)
    if product_type:
        qs = qs.filter(product_type=product_type)
    obj = qs.last()
    if not obj:
        raise_graphql_error("Product not found.", field_name="id")
    return obj


def get_optional_category(category_id):
    if not category_id:
        return None
    category = Category.objects.filter(id=category_id, is_deleted=False).last()
    if not category:
        raise_graphql_error("Category not found.", field_name="category")
    return category


def sync_attachments(product, attachments):
    if attachments is None:
        return
    product.attachments.all().delete()
    for attach in attachments:
        ProductAttachment.objects.create(
            product=product,
            file_url=attach.get('file_url'),
            file_id=attach.get('file_id'),
            is_cover=attach.get('is_cover'),
        )


def sync_ingredients(product, ingredients):
    if ingredients is None:
        return
    product.ingredients.clear()
    for ing in ingredients:
        product.ingredients.add(Ingredient.objects.get_or_create(name=ing)[0])


def sync_menu_items(product, menu_items):
    if menu_items is None:
        return
    existing_ids = []
    for index, item in enumerate(menu_items, start=1):
        item_id = item.get('id')
        defaults = {
            'title': item.get('title'),
            'allergens': item.get('allergens') or [],
            'image_url': item.get('image_url'),
            'file_id': item.get('file_id'),
            'order': item.get('order') or index,
            'is_deleted': False,
            'deleted_on': None,
        }
        if item_id:
            obj = product.menu_items.filter(id=item_id).last()
            if not obj:
                raise_graphql_error("Menu item not found.", field_name="menuItems")
            for key, value in defaults.items():
                setattr(obj, key, value)
            obj.save()
        else:
            obj = MenuItem.objects.create(product=product, **defaults)
        existing_ids.append(obj.id)
    product.menu_items.exclude(id__in=existing_ids).update(is_deleted=True, deleted_on=timezone.now())


def sync_optional_add_ons(product, optional_add_on_ids):
    if optional_add_on_ids is None:
        return
    add_ons = Product.objects.filter(
        id__in=optional_add_on_ids,
        vendor=product.vendor,
        product_type=ProductTypeChoices.ADD_ON,
        is_deleted=False,
    )
    if add_ons.count() != len(set(optional_add_on_ids)):
        raise_graphql_error("One or more add-ons are invalid.", field_name="optionalAddOnIds")
    product.optional_add_ons.set(add_ons)


def apply_menu_input(product, input_data, product_type):
    product.product_type = product_type
    product.name = input_data.get('name')
    product.title = input_data.get('title') or input_data.get('name')
    product.description = input_data.get('description') or ""
    product.category = get_optional_category(input_data.get('category'))
    product.price_with_tax = input_data.get('price_with_tax')
    product.tax_percent = input_data.get('tax_percent') or product.tax_percent
    product.menu_status = validate_choice(
        input_data.get('menu_status') or product.menu_status or MenuStatusChoices.DRAFT,
        MenuStatusChoices,
        "menuStatus",
    )
    product.dietary_tags = input_data.get('dietary_tags') or []
    product.custom_dietary = input_data.get('custom_dietary')
    product.contains = input_data.get('contains')
    if product_type == ProductTypeChoices.MENU:
        product.menu_type = input_data.get('menu_type')
        product.pricing_type = validate_choice(
            input_data.get('pricing_type') or product.pricing_type or PricingTypeChoices.PER_PERSON,
            PricingTypeChoices,
            "pricingType",
        )
        product.minimum_guests = input_data.get('minimum_guests') or 1
        product.min_lead_time_hours = input_data.get('min_lead_time_hours') or 24
        product.available_days = input_data.get('available_days') or []
        product.blackout_dates = input_data.get('blackout_dates') or []
        product.is_adjustable_for_single_staff = bool(input_data.get('is_adjustable_for_single_staff'))
    product.availability = product.menu_status == MenuStatusChoices.ACTIVE
    product.status = ProductStatusChoices.APPROVED
    product.save()
    return product


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
        form = VendorProductForm(data=input)
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = get_object_by_id(Product, object_id)
            form = VendorProductForm(data=input, instance=old_obj)
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


class VendorMenuMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        input = VendorMenuInput(required=True)
        ingredients = graphene.List(graphene.String)
        attachments = graphene.List(ProductAttachmentInput)
        menu_items = graphene.List(MenuItemInput)
        optional_add_on_ids = graphene.List(graphene.ID)

    @is_vendor_user
    def mutate(self, info, input, ingredients=None, attachments=None, menu_items=None, optional_add_on_ids=None):
        user = info.context.user
        product = Product(vendor=user.vendor)
        if input.get('id'):
            product = get_vendor_product(user, input.get('id'), ProductTypeChoices.MENU)
        product = apply_menu_input(product, input, ProductTypeChoices.MENU)
        sync_ingredients(product, ingredients)
        sync_attachments(product, attachments)
        sync_menu_items(product, menu_items)
        sync_optional_add_ons(product, optional_add_on_ids)
        return VendorMenuMutation(
            success=True,
            message=f"Successfully {'updated' if input.get('id') else 'created'}",
            instance=product,
        )


class VendorAddOnMutation(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        input = VendorAddOnInput(required=True)
        attachments = graphene.List(ProductAttachmentInput)

    @is_vendor_user
    def mutate(self, info, input, attachments=None):
        user = info.context.user
        product = Product(vendor=user.vendor)
        if input.get('id'):
            product = get_vendor_product(user, input.get('id'), ProductTypeChoices.ADD_ON)
        product = apply_menu_input(product, input, ProductTypeChoices.ADD_ON)
        sync_attachments(product, attachments)
        return VendorAddOnMutation(
            success=True,
            message=f"Successfully {'updated' if input.get('id') else 'created'}",
            instance=product,
        )


class VendorMenuStatusUpdate(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        id = graphene.ID(required=True)
        menu_status = graphene.String(required=True)

    @is_vendor_user
    def mutate(self, info, id, menu_status):
        validate_choice(menu_status, MenuStatusChoices, "menuStatus")
        product = get_vendor_product(info.context.user, id)
        product.menu_status = menu_status
        product.availability = menu_status == MenuStatusChoices.ACTIVE
        product.save()
        return VendorMenuStatusUpdate(
            success=True,
            message="Successfully updated",
            instance=product,
        )


class VendorMenuDelete(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID(required=True)

    @is_vendor_user
    def mutate(self, info, id):
        product = get_vendor_product(info.context.user, id)
        product.is_deleted = True
        product.deleted_on = timezone.now()
        product.save()
        product.menu_items.update(is_deleted=True, deleted_on=timezone.now())
        return VendorMenuDelete(success=True, message="Successfully deleted")


class VendorMenuDuplicate(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String()

    @is_vendor_user
    def mutate(self, info, id, name=None):
        source = get_vendor_product(info.context.user, id)
        source_ingredients = list(source.ingredients.all())
        source_add_ons = list(source.optional_add_ons.all())
        source_attachments = list(source.attachments.all())
        source_items = list(source.menu_items.filter(is_deleted=False))
        duplicate = Product.objects.create(
            name=name or f"{source.name} Copy",
            title=name or f"{source.name} Copy",
            description=source.description,
            category=source.category,
            vendor=source.vendor,
            contains=source.contains,
            discount_availability=source.discount_availability,
            is_adjustable_for_single_staff=source.is_adjustable_for_single_staff,
            is_featured=source.is_featured,
            order=source.order,
            status=source.status,
            note=source.note,
            product_type=source.product_type,
            menu_status=MenuStatusChoices.DRAFT,
            pricing_type=source.pricing_type,
            menu_type=source.menu_type,
            minimum_guests=source.minimum_guests,
            min_lead_time_hours=source.min_lead_time_hours,
            available_days=source.available_days,
            blackout_dates=source.blackout_dates,
            dietary_tags=source.dietary_tags,
            custom_dietary=source.custom_dietary,
            availability=False,
            price_with_tax=source.price_with_tax,
            tax_percent=source.tax_percent,
        )
        duplicate.ingredients.set(source_ingredients)
        duplicate.optional_add_ons.set(source_add_ons)
        for attach in source_attachments:
            ProductAttachment.objects.create(
                product=duplicate,
                file_url=attach.file_url,
                file_id=attach.file_id,
                is_cover=attach.is_cover,
            )
        for item in source_items:
            MenuItem.objects.create(
                product=duplicate,
                title=item.title,
                allergens=item.allergens,
                image_url=item.image_url,
                file_id=item.file_id,
                order=item.order,
            )
        return VendorMenuDuplicate(
            success=True,
            message="Successfully duplicated",
            instance=duplicate,
        )


class VendorMenuCopyItems(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductType)

    class Arguments:
        source_menu_id = graphene.ID(required=True)
        target_menu_id = graphene.ID(required=True)
        menu_item_ids = graphene.List(graphene.ID, required=True)

    @is_vendor_user
    def mutate(self, info, source_menu_id, target_menu_id, menu_item_ids):
        user = info.context.user
        source = get_vendor_product(user, source_menu_id, ProductTypeChoices.MENU)
        target = get_vendor_product(user, target_menu_id, ProductTypeChoices.MENU)
        items = source.menu_items.filter(id__in=menu_item_ids, is_deleted=False)
        if items.count() != len(set(menu_item_ids)):
            raise_graphql_error("One or more menu items are invalid.", field_name="menuItemIds")
        start_order = target.menu_items.filter(is_deleted=False).count() + 1
        for index, item in enumerate(items, start=start_order):
            MenuItem.objects.create(
                product=target,
                title=item.title,
                allergens=item.allergens,
                image_url=item.image_url,
                file_id=item.file_id,
                order=index,
            )
        return VendorMenuCopyItems(
            success=True,
            message="Successfully copied",
            instance=target,
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
    vendor_menu_mutation = VendorMenuMutation.Field()
    vendor_add_on_mutation = VendorAddOnMutation.Field()
    vendor_menu_status_update = VendorMenuStatusUpdate.Field()
    vendor_menu_delete = VendorMenuDelete.Field()
    vendor_menu_duplicate = VendorMenuDuplicate.Field()
    vendor_menu_copy_items = VendorMenuCopyItems.Field()
    verify_vendor_product = VerifyVendorProduct.Field()
    food_meeting_mutation = FoodMeetingMutation.Field()
    food_meeting_resolve = FoodMeetingResolve.Field()
    food_meeting_delete = MeetingDeleteMutation.Field()
    favorite_product_mutation = FavoriteProductMutation.Field()
    weekly_variant_products = WeeklyVariantProductMutation.Field()
