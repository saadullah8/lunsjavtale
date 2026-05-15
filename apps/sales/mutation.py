import graphene
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from graphene_django.forms.mutation import DjangoFormMutation, DjangoModelFormMutation
from graphene_django.forms.types import DjangoFormInputObjectType
from graphql import GraphQLError

# local imports
from apps.bases.utils import (
    camel_case_format,
    raise_graphql_error,
    raise_graphql_error_with_fields,
)
from apps.notifications.tasks import (
    notify_company_order_update,
    notify_order_placed,
    send_admin_notification_and_save,
    send_admin_sell_order_mail,
    user_cart_added_notification,
    user_cart_request_confirmed_notification,
    user_cart_update_confirmed_notification,
    user_cart_update_notification,
)
from apps.scm.models import Ingredient, Product
from apps.users.choices import RoleTypeChoices
from backend.task_dispatch import dispatch_task
from backend.permissions import is_admin_user, is_vendor_user, is_authenticated, is_company_user

from ..notifications.choices import NotificationTypeChoice
from ..users.models import Coupon
from .choices import (
    DecisionChoices,
    InvoiceStatusChoices,
    OrderPaymentTypeChoices,
    PaymentStatusChoices,
    PaymentTypeChoices,
)
from .forms import (
    BillingAddressForm,
    CompanyOrderPaymentForm,
    OrderPaymentForm,
    PaymentMethodForm,
    ProductRatingForm,
)
from .models import (
    AlterCart,
    BillingAddress,
    Order,
    OrderPayment,
    OrderStatus,
    PaymentMethod,
    ProductRating,
    SellCart,
    UserCart,
)
from .object_types import (
    OrderPaymentType,
    OrderType,
    PaymentMethodType,
    ProductRatingType,
)
from .tasks import (
    add_user_carts,
    make_online_payment,
    make_previous_payment,
    notify_user_carts,
    vendor_sold_amount_calculation,
)

User = get_user_model()


class PaymentMethodMutation(DjangoModelFormMutation):
    """
        update and create new PaymentMethod information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(PaymentMethodType)

    class Meta:
        form_class = PaymentMethodForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = PaymentMethodForm(data=input)
        object_id = None
        if form.data.get('id'):
            object_id = form.data['id']
            old_obj = PaymentMethod.objects.get(user=user, id=object_id)
            form = PaymentMethodForm(data=input, instance=old_obj)
        form_data = form.data
        if form.is_valid():
            form_data['user'] = user
            obj, created = PaymentMethod.objects.update_or_create(id=object_id, defaults=form_data)
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
        return PaymentMethodMutation(
            success=True, message=f"Successfully {'added' if created else 'updated'}", instance=obj
        )


class PaymentMethodDeleteMutation(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_authenticated
    def mutate(self, info, id, **kwargs):
        obj = PaymentMethod.objects.get(id=id, is_deleted=False, user=info.context.user)
        obj.is_deleted = True
        obj.deleted_on = timezone.now()
        obj.save()
        return PaymentMethodDeleteMutation(
            success=True, message="Successfully deleted"
        )


class CartInput(graphene.InputObjectType):
    date = graphene.Date()
    quantity = graphene.Int()
    added_for = graphene.List(graphene.ID, required=False)


class AddToCart(graphene.Mutation):
    success = graphene.Boolean()

    class Arguments:
        item = graphene.ID()
        ingredients = graphene.List(graphene.ID)
        dates = graphene.List(CartInput)

    @is_authenticated
    def mutate(self, info, item, ingredients, dates):
        user = info.context.user
        if user.role not in [RoleTypeChoices.COMPANY_OWNER, RoleTypeChoices.COMPANY_MANAGER, RoleTypeChoices.COMPANY_EMPLOYEE]:
            raise_graphql_error("User not permitted.")
        item = Product.objects.get(id=item)
        for qt in dates:
            cart, created = SellCart.objects.get_or_create(item=item, added_by=user, date=qt['date'])
            cart.quantity = qt['quantity'] if user.role != RoleTypeChoices.COMPANY_EMPLOYEE else 1
            cart.price = item.actual_price
            cart.price_with_tax = item.price_with_tax
            cart.save()
            cart.ingredients.add(*Ingredient.objects.filter(id__in=ingredients))
            cart.added_for.clear()
            cart.added_for.add(*User.objects.filter(company=user.company, id__in=qt.get('added_for', [])))
        return AddToCart(
            success=True
        )


class RemoveCart(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_authenticated
    def mutate(self, info, id, **kwargs):
        user = info.context.user
        carts = user.added_carts.all()
        obj = carts.get(id=id)
        obj.delete()
        return RemoveCart(
            success=True,
            message="Successfully removed",
        )


class EditCartMutation(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        quantity = graphene.Int()
        added_for = graphene.List(graphene.ID)

    @is_company_user
    def mutate(self, info, id, quantity, added_for, **kwargs):
        user = info.context.user
        company = user.company
        carts = SellCart.objects.filter(Q(added_by=user) | Q(order__company=user.company))
        obj = carts.get(
            Q(order__isnull=True) | Q(order__status__in=[
                InvoiceStatusChoices.PLACED, InvoiceStatusChoices.UPDATED, InvoiceStatusChoices.PAYMENT_PENDING
            ]), id=id
        )
        company_due_amount = obj.order.company_due_amount

        staffs = User.objects.filter(company=user.company, id__in=added_for)
        if staffs.count() > quantity:
            raise_graphql_error("Quantity is not valid for the added employees.")
        obj.quantity = quantity
        obj.save()
        obj.added_for.clear()
        obj.added_for.add(*staffs)
        if obj.order:
            obj.order.save()
            OrderStatus.objects.create(order=obj.order, status=InvoiceStatusChoices.UPDATED)
        company.invoice_amount += obj.order.company_due_amount - company_due_amount
        company.save()
        add_user_carts.delay(obj.id)
        return EditCartMutation(
            success=True,
            message="Successfully updated",
        )


class SendCartRequest(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    @is_authenticated
    def mutate(self, info, **kwargs):
        user = info.context.user
        carts = user.added_carts.all()
        if not carts.exists():
            raise_graphql_error("No item added.")
        carts.update(is_requested=True)
        user_cart_added_notification.delay(carts.last().id)
        return SendCartRequest(
            success=True,
            message="Successfully requested",
        )


class RemoveProductCart(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()

    @is_authenticated
    def mutate(self, info, id, **kwargs):
        user = info.context.user
        carts = user.added_carts.all()
        obj = carts.filter(item__id=id)
        obj.delete()
        return RemoveProductCart(
            success=True,
            message="Successfully removed",
        )


class ApproveCart(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderType)

    class Arguments:
        ids = graphene.List(graphene.ID, required=True)
        request_status = graphene.String()

    @is_company_user
    def mutate(self, info, ids, request_status, **kwargs):
        user = info.context.user
        if request_status not in [DecisionChoices.ACCEPTED, DecisionChoices.REJECTED]:
            raise_graphql_error("Please select a valid option.", field_name="requestStatus")
        carts = SellCart.objects.filter(
            added_by__role=RoleTypeChoices.COMPANY_EMPLOYEE, added_by__company=user.company, id__in=ids,
            is_requested=True, request_status=DecisionChoices.PENDING
        )
        if not carts:
            raise_graphql_error("No carts found.", field_name="ids")
        for qt in carts:
            if request_status == DecisionChoices.ACCEPTED:
                user_cart_request_confirmed_notification.delay(qt.added_by.id, qt.item.name)
            cart, created = SellCart.objects.get_or_create(item=qt.item, added_by=user, date=qt.date)
            cart.quantity = 1 if created else cart.quantity + 1
            cart.price = qt.item.actual_price
            cart.price_with_tax = qt.item.price_with_tax
            cart.request_status = request_status
            cart.save()
            cart.ingredients.add(*qt.item.ingredients.all())
            cart.added_for.add(qt.added_by)
            qt.delete()
        return ApproveCart(
            success=True,
            message="Item added to cart.",
        )


class BillingAddressInput(DjangoFormInputObjectType):
    class Meta:
        form_class = BillingAddressForm


class OrderCreation(graphene.Mutation):
    success = graphene.Boolean()
    payment_url = graphene.String()

    class Arguments:
        payment_type = graphene.String()
        shipping_address = graphene.ID()
        billing_address = BillingAddressInput()
        company_allowance = graphene.Int()

    @is_company_user
    @transaction.atomic
    def mutate(self, info, payment_type, shipping_address, billing_address, company_allowance=0):
        user = info.context.user
        company = user.company
        if payment_type not in OrderPaymentTypeChoices:
            raise_graphql_error("Please select a valid payment-type.")
        carts = user.added_carts.all()
        if not carts.exists():
            raise_graphql_error("Please add carts first.")
        try:
            shipping_address = company.addresses.get(id=shipping_address)
        except Exception:
            raise_graphql_error("Invalid shipping address", field_name="shippingAddress")
        billing_form = BillingAddressForm(data=billing_address)
        if not billing_form.is_valid():
            error_data = {}
            for error in billing_form.errors:
                for err in billing_form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        billing_form_data = billing_form.data
        dates = set(list(carts.values_list('date', flat=True)))
        total_invoice_amount = 0
        orders = []
        payment_url = None
        for date in dates:
            obj = Order.objects.create(
                company=company, created_by=user, payment_type=payment_type,
                company_allowance=company_allowance, shipping_address=shipping_address,
                delivery_date=date
            )
            orders.append(obj)
            billing_form_data['order'] = obj
            BillingAddress.objects.create(**billing_form_data)
            OrderStatus.objects.create(order=obj, status=InvoiceStatusChoices.PLACED)
            date_carts = carts.filter(date=date)
            date_carts.update(added_by=None, order=obj)
            obj.save()
            invoice_amount = obj.company_due_amount
            company.invoice_amount += invoice_amount
            company.ordered_amount += obj.final_price
            company.save()
            total_invoice_amount += invoice_amount
            if payment_type == OrderPaymentTypeChoices.ONLINE:
                OrderStatus.objects.create(order=obj, status=InvoiceStatusChoices.PAYMENT_PENDING)
        if payment_type == OrderPaymentTypeChoices.ONLINE:
            payment = OrderPayment.objects.create(
                company=company, payment_type=OrderPaymentTypeChoices.ONLINE, paid_amount=total_invoice_amount,
                created_by=user
            )
            payment.orders.add(*orders)
            payment_url = make_online_payment(payment.id)
        notify_order_placed.delay(company.id, list(map(lambda i: i.id, orders)))
        send_admin_notification_and_save.delay(
            title="New Order placed",
            message=f"New orders placed by '{company.name}'",
            object_id=str(company.id),
            n_type=NotificationTypeChoice.ORDER_PLACED
        )
        for obj in orders:
            obj.save()
            notify_user_carts.delay(list(obj.order_carts.all().values_list('id', flat=True)))
        send_admin_sell_order_mail.delay(
            company.id, list(map(lambda i: {
                'id': i.id, 'delivery_date': i.delivery_date, 'final_price': i.final_price
            }, orders))
        )
        return OrderCreation(
            success=True, payment_url=payment_url
        )


class OrderStatusUpdate(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderType)

    class Arguments:
        id = graphene.ID()
        status = graphene.String()
        note = graphene.String()

    @is_vendor_user
    def mutate(self, info, id, status="", note=""):
        from .models import ClientOrder
        from apps.users.models import RewardTransaction
        user = info.context.user
        
        # Try finding in Corporate Orders
        obj = Order.objects.filter(id=id, is_deleted=False, order_carts__item__vendor=user.vendor).distinct().last()
        is_client_order = False
        
        if not obj:
            # Try finding in Client Orders
            obj = ClientOrder.objects.filter(id=id, vendor=user.vendor).last()
            is_client_order = True
            
        if not obj:
            raise_graphql_error("Order not found.", field_name="id")
            
        if obj.status in [InvoiceStatusChoices.CANCELLED, InvoiceStatusChoices.DELIVERED]:
            raise_graphql_error(f"Order status already in '{obj.status}'")
            
        # Update Status
        if is_client_order:
            obj.status = status
            obj.save()
        else:
            OrderStatus.objects.create(order=obj, status=status, note=note)
            
        dispatch_task(notify_company_order_update, obj.id)
        
        # Award Reward Points on Delivery
        if status == InvoiceStatusChoices.DELIVERED:
            if not is_client_order:
                dispatch_task(vendor_sold_amount_calculation, obj.id)
            
            # Logic for Rewards
            order_user = obj.created_by if not is_client_order else obj.user
            if order_user and order_user.rewards_enabled:
                points = int(obj.total_amount if is_client_order else obj.final_price)
                if points > 0:
                    order_user.reward_points += points
                    order_user.save()
                    RewardTransaction.objects.create(
                        user=order_user,
                        transaction_type=RewardTransaction.EARN,
                        source=RewardTransaction.SOURCE_ORDER,
                        points=points,
                        description=f"Points earned from order #{obj.id}"
                    )

        return OrderStatusUpdate(
            success=True,
            message="Successfully updated",
        )


class OrderHistoryDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderType)

    class Arguments:
        id = graphene.ID()

    @is_admin_user
    def mutate(self, info, id, **kwargs):
        obj = Order.objects.get(
            id=id
        )
        obj.is_deleted = True
        obj.deleted_on = timezone.now()
        obj.save()
        return OrderHistoryDelete(
            success=True,
            message="Successfully deleted",
        )


class PaymentHistoryDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderType)

    class Arguments:
        ids = graphene.List(graphene.ID)

    @is_admin_user
    def mutate(self, info, ids, **kwargs):
        payments = OrderPayment.objects.filter(
            id__in=ids
        )
        payments.update(is_deleted=True, deleted_on=timezone.now())
        return PaymentHistoryDelete(
            success=True,
            message="Successfully deleted",
        )


class SalesHistoryDelete(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderType)

    class Arguments:
        ids = graphene.List(graphene.ID)

    @is_admin_user
    def mutate(self, info, ids, **kwargs):
        qs = SellCart.objects.filter(
            id__in=ids
        )
        qs.update(is_deleted=True, deleted_on=timezone.now())
        return SalesHistoryDelete(
            success=True,
            message="Successfully deleted",
        )


class UserCartUpdate(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        item = graphene.ID()

    @is_authenticated
    def mutate(self, info, id, item):
        user = info.context.user
        obj = SellCart.objects.get(
            id=id, added_for=user
        )
        if obj.order.status not in [
            InvoiceStatusChoices.PLACED, InvoiceStatusChoices.UPDATED, InvoiceStatusChoices.PAYMENT_PENDING,
            InvoiceStatusChoices.PAYMENT_COMPLETED
        ]:
            raise_graphql_error(f"Order already in '{obj.order.status}'")
        product = Product.objects.get(id=item, category=obj.item.category)
        user_cart = UserCart.objects.get(cart=obj, added_for=user)
        AlterCart.objects.get_or_create(
            base=user_cart, previous_cart=obj, item=product
        )
        user_cart_update_notification.delay(user_cart.id)
        return UserCartUpdate(
            success=True,
            message="Successfully updated",
        )


class UserCartIngredientUpdate(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        ingredients = graphene.List(graphene.ID)

    @is_authenticated
    def mutate(self, info, id, ingredients):
        user = info.context.user
        obj = User.objects.get(
            id=id, added_for=user
        )
        obj.ingredients.clear()
        obj.ingredients.add(*Ingredient.objects.filter(id__in=ingredients))
        return UserCartIngredientUpdate(
            success=True,
            message="Successfully updated",
        )


class ConfirmUserCartUpdate(graphene.Mutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        id = graphene.ID()
        status = graphene.String()

    @is_company_user
    def mutate(self, info, id, status):
        user = info.context.user
        company = user.company
        obj = AlterCart.objects.get(
            id=id, base__added_for__company=company
        )
        if obj.base.cart.order.status not in [
            InvoiceStatusChoices.PLACED, InvoiceStatusChoices.UPDATED, InvoiceStatusChoices.PAYMENT_PENDING,
            InvoiceStatusChoices.PAYMENT_COMPLETED
        ]:
            raise_graphql_error(f"Order already in '{obj.order.status}'")
        if status not in [DecisionChoices.ACCEPTED, DecisionChoices.REJECTED]:
            raise_graphql_error("Invalid action")
        if status == DecisionChoices.ACCEPTED:
            company_due_amount = obj.previous_cart.order.company_due_amount
            cart, c = SellCart.objects.get_or_create(
                order=obj.previous_cart.order, item=obj.item, date=obj.previous_cart.date
            )
            if c:
                cart.price = obj.item.actual_price
                cart.price_with_tax = obj.item.price_with_tax
            else:
                cart.quantity += 1
            cart.save()
            cart.added_for.add(obj.base.added_for)
            obj.base.cart = cart
            obj.base.save()
            obj.previous_cart.added_for.remove(obj.base.added_for)
            obj.previous_cart.cancelled_by.add(obj.base.added_for)
            obj.previous_cart.cancelled += 1
            obj.previous_cart.save()
            cart.order.save()
            obj.status = DecisionChoices.ACCEPTED
            obj.save()
            OrderStatus.objects.create(order=cart.order, status=InvoiceStatusChoices.UPDATED)

            company.invoice_amount += cart.order.company_due_amount - company_due_amount
            company.save()

            user_cart_update_confirmed_notification.delay(obj.id)
        else:
            obj.status = DecisionChoices.REJECTED
            obj.save()
        return ConfirmUserCartUpdate(
            success=True,
            message="Successfully updated",
        )


class AddProductRating(DjangoFormMutation):
    """
    """

    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductRatingType)

    class Meta:
        form_class = ProductRatingForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = ProductRatingForm(data=input)
        if form.is_valid():
            cart_item = user.cart_items.filter(cart__item=form.cleaned_data['product']).select_related('cart__order').last()
            if not cart_item:
                raise_graphql_error("User not permitted to rate this product.")
            form.cleaned_data['added_by'] = user
            form.cleaned_data['order'] = cart_item.cart.order
            obj = form.save()
            
            # Award Reward Points for Review
            from apps.users.models import RewardTransaction
            if user.rewards_enabled:
                points = 1000
                user.reward_points += points
                user.save()
                RewardTransaction.objects.create(
                    user=user,
                    transaction_type=RewardTransaction.EARN,
                    source=RewardTransaction.SOURCE_REVIEW,
                    points=points,
                    description=f"Points earned for reviewing order #{obj.order.id if obj.order else 'N/A'}"
                )
        else:
            error_data = {}
            for error in form.errors:
                for err in form.errors[error]:
                    error_data[camel_case_format(error)] = err
            raise_graphql_error_with_fields("Invalid input request.", error_data)
        return AddProductRating(
            success=True,
            message="Successfully added",
            instance=obj
        )


class VendorReviewReply(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(ProductRatingType)

    class Arguments:
        id = graphene.ID(required=True)
        reply_text = graphene.String(required=True)
        attention_required = graphene.Boolean()

    @is_vendor_user
    def mutate(self, info, id, reply_text, attention_required=None):
        review = ProductRating.objects.filter(
            id=id,
            product__vendor=info.context.user.vendor,
        ).last()
        if not review:
            raise_graphql_error("Review not found.", field_name="id")
        if not str(reply_text).strip():
            raise_graphql_error("Reply text is required.", field_name="replyText")
        review.reply_text = str(reply_text).strip()
        review.replied_on = timezone.now()
        if attention_required is not None:
            review.attention_required = attention_required
        review.is_checked = True
        review.save()
        return VendorReviewReply(
            success=True,
            message="Reply posted.",
            instance=review,
        )


class OrderPaymentMutation(DjangoFormMutation):
    """
        update and create new PaymentMethod information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    instance = graphene.Field(OrderPaymentType)

    class Meta:
        form_class = OrderPaymentForm

    @is_admin_user
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = OrderPaymentForm(data=input)
        if form.is_valid():
            orders = form.cleaned_data.pop('orders')
            obj = form.save(commit=False)
            obj.created_by = user
            obj.payment_type = PaymentTypeChoices.CASH
            obj.status = PaymentStatusChoices.COMPLETED
            obj.save()
            if orders:
                obj.orders.add(*Order.objects.filter(id__in=orders))
            make_previous_payment.delay(obj.id)
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
        return OrderPaymentMutation(
            success=True, message="Successfully created", instance=obj
        )


class MakeOnlinePaymentMutation(DjangoFormMutation):
    """
        update and create new PaymentMethod information by some default fields.
    """
    success = graphene.Boolean()
    message = graphene.String()
    payment_url = graphene.String()
    instance = graphene.Field(OrderPaymentType)

    class Meta:
        form_class = CompanyOrderPaymentForm

    @is_authenticated
    def mutate_and_get_payload(self, info, **input):
        user = info.context.user
        form = CompanyOrderPaymentForm(data=input)
        if form.is_valid():
            if user.company != form.cleaned_data.get('company'):
                raise_graphql_error("Please select valid company.", field_name="company")
            orders = form.cleaned_data.pop('orders')
            user_carts = form.cleaned_data.pop('user_carts')
            obj = form.save(commit=False)
            obj.created_by = user
            obj.payment_type = PaymentTypeChoices.ONLINE
            obj.save()
            if orders:
                obj.orders.add(*Order.objects.filter(id__in=orders))
            if user_carts:
                obj.user_carts.add(*UserCart.objects.filter(id__in=user_carts))
            payment_url = make_online_payment(obj.id)
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
        return MakeOnlinePaymentMutation(
            success=True, message="Successfully created", instance=obj, payment_url=payment_url
        )


class InitiatePendingPayment(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()
    payment_url = graphene.String()

    class Arguments:
        id = graphene.Float()

    @is_authenticated
    def mutate(self, info, id, **kwargs):
        payment = OrderPayment.objects.get(
            id=id, payment_type=PaymentTypeChoices.ONLINE, status=PaymentStatusChoices.PENDING
        )
        payment_url = make_online_payment(payment.id)
        return InitiatePendingPayment(
            success=True, message="Successfully initiated", payment_url=payment_url
        )


class ApplyCoupon(graphene.Mutation):
    """
    """
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        coupon = graphene.String()
        order_id = graphene.Float()

    @is_admin_user
    def mutate(self, info, coupon, order_id, **kwargs):
        try:
            coupon = Coupon.objects.get(name=coupon)
        except Exception:
            raise_graphql_error("Invalid promo-code.", field_name="coupon")
        order = Order.objects.get(id=order_id)
        amount_discounted, price = coupon.get_discounted_price(order.final_price)
        # order.final_price = price
        order.discount_amount = amount_discounted
        order.coupon = coupon
        order.save()
        return ApplyCoupon(
            success=True, message="Successfully applied"
        )


class ClientOrderItemInput(graphene.InputObjectType):
    product = graphene.ID(required=True)
    quantity = graphene.Int(required=True)

class PlaceClientOrder(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        vendor_id = graphene.ID(required=True)
        customer_type = graphene.String(required=True) # 'Corporate' or 'Private'
        
        # Corporate specific (Optional)
        corporate_name = graphene.String()
        organization_number = graphene.String()
        invoice_reference = graphene.String()
        
        # Contact & Address (Optional - will auto-fill from Profile/Default Addresses)
        email = graphene.String()
        phone = graphene.String()
        delivery_address = graphene.String()
        invoice_address = graphene.String()
        invoice_suite = graphene.String()
        invoice_postal_code = graphene.String()
        invoice_city = graphene.String()
        
        # Event Details
        event_name = graphene.String()
        event_date = graphene.Date()
        event_time = graphene.Time()
        person_count = graphene.Int()
        
        # Pricing & Totals
        tip_amount = graphene.Decimal()
        tax_percent = graphene.Decimal()
        
        # Additional Info
        order_notes = graphene.String()
        items = graphene.List(ClientOrderItemInput, required=True)

    @is_authenticated
    def mutate(self, info, vendor_id, items, **kwargs):
        from apps.users.models import Vendor, Address
        from apps.scm.models import Product
        from .models import ClientOrder, ClientOrderItem
        
        user = info.context.user
        vendor = Vendor.objects.get(id=vendor_id)
        
        # --- AUTO-FILL LOGIC ---
        customer_type = kwargs.get('customer_type')
        
        # 1. Contact Info
        email = kwargs.get('email') or user.email
        phone = kwargs.get('phone') or user.phone
        
        # 2. Corporate Info
        corp_name = kwargs.get('corporate_name')
        if not corp_name and customer_type == 'Corporate':
            corp_name = user.company_name or (user.company.name if user.company else None)
            
        # 3. Addresses
        del_addr = kwargs.get('delivery_address')
        if not del_addr:
            default_delivery = user.addresses.filter(address_type='delivery', default=True).last()
            if default_delivery:
                del_addr = f"{default_delivery.location_name + ': ' if default_delivery.location_name else ''}{default_delivery.address}"
                if default_delivery.unit_floor: del_addr += f", {default_delivery.unit_floor}"
                if default_delivery.city: del_addr += f", {default_delivery.city}"
        
        inv_addr = kwargs.get('invoice_address')
        inv_suite = kwargs.get('invoice_suite')
        inv_post = kwargs.get('invoice_postal_code')
        inv_city = kwargs.get('invoice_city')
        
        if not inv_addr:
            default_invoice = user.addresses.filter(address_type='invoice', default=True).last()
            if default_invoice:
                inv_addr = default_invoice.address
                inv_suite = default_invoice.unit_floor
                inv_post = default_invoice.post_code
                inv_city = default_invoice.city
        
        # --- CALCULATE DUE DATE (5 Days after Event) ---
        from datetime import timedelta, datetime
        event_date = kwargs.get('event_date')
        due_date = None
        if event_date:
            if isinstance(event_date, str):
                event_date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
            else:
                event_date_obj = event_date
            due_date = event_date_obj + timedelta(days=5)

        # --- CREATE ORDER ---
        order = ClientOrder.objects.create(
            user=user,
            vendor=vendor,
            customer_type=customer_type,
            company_name=corp_name,
            organization_number=kwargs.get('organization_number'),
            invoice_reference=kwargs.get('invoice_reference'),
            email=email,
            phone=phone,
            delivery_address_str=del_addr or "N/A",
            invoice_address_str=inv_addr or "N/A",
            invoice_suite=inv_suite,
            invoice_postal_code=inv_post,
            invoice_city=inv_city,
            event_name=kwargs.get('event_name'),
            event_date=kwargs.get('event_date'),
            event_time=kwargs.get('event_time'),
            due_date=due_date,
            person_count=kwargs.get('person_count', 1),
            order_notes=kwargs.get('order_notes'),
        )
        
        total = 0
        for item in items:
            prod = Product.objects.get(id=item.product)
            quantity = item.quantity
            unit_price = prod.actual_price or 0
            item_total = unit_price * quantity
            total += item_total
            
            ClientOrderItem.objects.create(
                order=order,
                product=prod,
                product_name=prod.title or prod.name or "Product",
                quantity=quantity,
                unit_price=unit_price,
                total_price=item_total
            )
            
        # Financial Calculations
        order.total_amount = total
        
        # Calculate Tax
        from decimal import Decimal
        tax_pct = Decimal(str(kwargs.get('tax_percent') or getattr(settings, 'TAX_PERCENTAGE', 15)))
        order.tax_amount = (total * tax_pct) / Decimal('100')
        
        # Delivery Fee
        order.delivery_fee = vendor.delivery_settings.base_delivery_fee if hasattr(vendor, 'delivery_settings') else 0
        
        # Tip
        order.tip_amount = kwargs.get('tip_amount') or 0
        
        # Grand Total
        order.grand_total = order.total_amount + order.tax_amount + order.delivery_fee + order.tip_amount
        order.save()
        
        return PlaceClientOrder(success=True, message="Order placed successfully")


class Mutation(graphene.ObjectType):
    """
        define all the mutations by identifier name for query
    """
    payment_method_mutation = PaymentMethodMutation.Field()
    delete_payment_method = PaymentMethodDeleteMutation.Field()
    add_product_rating = AddProductRating.Field()
    vendor_review_reply = VendorReviewReply.Field()

    add_to_cart = AddToCart.Field()
    send_cart_request = SendCartRequest.Field()
    remove_cart = RemoveCart.Field()
    cart_update = EditCartMutation.Field()
    remove_product_cart = RemoveProductCart.Field()
    approve_cart_request = ApproveCart.Field()
    user_cart_update = UserCartUpdate.Field()
    user_cart_ingredients_update = UserCartIngredientUpdate.Field()
    confirm_user_cart_update = ConfirmUserCartUpdate.Field()
    sales_history_delete = SalesHistoryDelete.Field()

    place_order = OrderCreation.Field()
    place_client_order = PlaceClientOrder.Field()
    order_status_update = OrderStatusUpdate.Field()
    order_history_delete = OrderHistoryDelete.Field()
    apply_coupon = ApplyCoupon.Field()

    create_payment = OrderPaymentMutation.Field()
    payment_history_delete = PaymentHistoryDelete.Field()
    make_online_payment = MakeOnlinePaymentMutation.Field()
    initiate_pending_payment = InitiatePendingPayment.Field()
