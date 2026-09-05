from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import (
    ORDER_WINDOW_DAYS,
    Checkout,
    Customer,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
    ResetAccountToken,
    WeeklyDelivery,
)
from .serializers import (
    CustomerSerializer,
    DeliveryDateSerializer,
    IngredientSerializer,
    OrderLineSerializer,
    OrderSerializer,
    ProductLineSerializer,
    ProductSerializer,
    WeeklyDeliverySerializer,
)


def staff_required(view_func):
    """login_required + staff check, returning 403 (not a redirect) for authenticated non-staff users."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


# REST FRAMEWORK


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all().order_by("id")
    serializer_class = IngredientSerializer
    permission_classes = [permissions.IsAdminUser]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("id")
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAdminUser]


class ProductLineViewSet(viewsets.ModelViewSet):
    queryset = ProductLine.objects.all().order_by("id")
    serializer_class = ProductLineSerializer
    permission_classes = [permissions.IsAdminUser]


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by("id")
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAdminUser]


class WeeklyDeliveryViewSet(viewsets.ModelViewSet):
    queryset = WeeklyDelivery.objects.all().order_by("id")
    serializer_class = WeeklyDeliverySerializer
    permission_classes = [permissions.IsAdminUser]


class DeliveryDateViewSet(viewsets.ModelViewSet):
    queryset = DeliveryDate.objects.all().filter(active=True).filter(date__gte=date.today()).order_by("id")
    serializer_class = DeliveryDateSerializer
    permission_classes = [permissions.IsAdminUser]


class OrderFilter(filters.FilterSet):
    min_date = filters.DateFilter(field_name="delivery_date__date", lookup_expr="gte")
    max_date = filters.DateFilter(field_name="delivery_date__date", lookup_expr="lte")

    class Meta:
        model = Order
        fields = "__all__"


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("id")
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_class = OrderFilter


class OrderLineViewSet(viewsets.ModelViewSet):
    queryset = OrderLine.objects.all().order_by("id")
    serializer_class = OrderLineSerializer
    permission_classes = [permissions.IsAdminUser]


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def generate_delivery_dates(request):
    for dday in WeeklyDelivery.objects.filter(active=True):
        dday.generate_delivery_dates()
    return Response({"message": "Delivery dates generated!"})


def _get_actions(target_date):
    delivery_dates = (
        DeliveryDate.objects.filter(date__gte=target_date)
        .filter(active=True)
        .filter(date__lte=target_date + timedelta(days=2))
        .select_related("weekly_delivery")
        .prefetch_related("order_set__lines__product__orig_product__raw_ingredients__ingredient")
    )
    actions = None
    for delivery_date in delivery_dates:
        for order in delivery_date.order_set.filter(validated=True):
            actions = order.get_actions(target_date, actions)
    if actions:
        actions.finalize()
    return actions


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def get_actions(request, year, month, day):
    return Response(_get_actions(date(year, month, day)))


# REGULAR VIEWS


@login_required
def index(request):
    if request.user.is_staff:
        return redirect("boulange:actions")
    return redirect("boulange:orders")


def account_init(request):
    email = request.POST.get("email")
    if not email:
        return redirect("boulange:index")
    customer = Customer.objects.filter(email=email).first()
    # Always render the same confirmation page so the response does not reveal
    # whether an account exists for the submitted address (avoid user enumeration).
    if customer is not None:
        # Throttle: don't send a fresh link (nor create a token) if one was already
        # issued recently, to prevent using this endpoint for email bombing.
        recently = timezone.now() - timedelta(minutes=10)
        if not ResetAccountToken.objects.filter(customer=customer, created__gte=recently).exists():
            token = ResetAccountToken(customer=customer)
            token.save()
            send_mail(
                "Boulangerie de la Ferme du Resto : initialisation de votre compte",
                f"""Bonjour,\n
Rendez-vous à l'adresse suivante pour positionner le mot de passe de votre compte :\n
{request.build_absolute_uri('/reset_password/'+str(token.token))}\n
Ce lien est valable 24h.\n
Attention : votre nom d'utilisateur/identifiant pour l'accès au service est : {customer.username}""",
                "boulangerie@lafermebioduresto.bzh",
                [customer.email],
                fail_silently=False,
            )
    return render(request, "registration/account_init.html")


def reset_password(request, token):
    token = get_object_or_404(ResetAccountToken, token=token)
    # Enforce expiry before doing anything else, so an expired token can't be used
    # to set a password through a POST request either.
    if (timezone.now() - token.created) > timedelta(days=1):
        return HttpResponse("Ce lien n'est plus valide")
    if request.POST:
        if len(request.POST.get("newpw", "")) < 8:
            return redirect("boulange:reset_password", token=token.token)
        else:
            token.customer.set_password(request.POST["newpw"])
            token.customer.save()
            token.delete()
            return redirect("boulange:index")

    context = {"token": token}
    return render(request, "registration/reset_password.html", context=context)


def _get_start_end_command_period():
    available_timespan_start = (timezone.localtime() + timedelta(days=1, hours=12)).date()
    available_timespan_end = date.today() + timedelta(days=ORDER_WINDOW_DAYS)
    return available_timespan_start, available_timespan_end


def _available_weekly_deliveries(user):
    """The weekly deliveries a customer is allowed to order from.

    Pros order on their own delivery points; everybody else gets the public ones
    plus the private ones they have explicitly been granted.
    """
    if user.is_professional and WeeklyDelivery.objects.filter(customer=user).exists():
        return WeeklyDelivery.objects.filter(customer=user).select_related("customer")
    return WeeklyDelivery.objects.filter(active=True).filter(Q(public_delivery_point=True) | Q(id__in=user.private_weekly_deliveries.all())).select_related("customer")


def _validate_order_submission(user, delivery_date_id, product_ids, product_qtys):
    """Re-check a submitted order server-side and return (delivery_date, lines).

    The form only ever offers dates and products the customer may pick, but the POST
    is attacker-controlled, so nothing from it is trusted: the delivery date is
    resolved through the customer's own allowed deliveries and the open ordering
    window, and every product is looked up in what that delivery actually sells that
    day. Anything off-limits is a 403. Non-positive quantities are dropped rather
    than refused, so a blank or 0 field simply means "no line" (and a negative one
    can never lower the cart total sent to SumUp).
    """
    available_timespan_start, available_timespan_end = _get_start_end_command_period()
    delivery_date = (
        DeliveryDate.objects.filter(id=delivery_date_id, active=True)
        .filter(date__gte=available_timespan_start)
        .filter(date__lte=available_timespan_end)
        .filter(weekly_delivery__in=_available_weekly_deliveries(user))
        .select_related("weekly_delivery")
        .first()
    )
    if delivery_date is None:
        raise PermissionDenied
    available_products = {product.id: product for product in delivery_date.weekly_delivery.get_available_products()}
    lines = []
    for product_id, qty in zip(product_ids, product_qtys):
        if not qty:
            continue
        try:
            product = available_products[int(product_id)]
            quantity = int(qty)
        except (KeyError, TypeError, ValueError):
            raise PermissionDenied
        if quantity > 0:
            lines.append((product, quantity))
    return delivery_date, lines


@login_required
def hx_get_dates_for_weekly_delivery(request):
    # Resolved through the customer's own deliveries: an arbitrary id would otherwise
    # list the dates of a private delivery point they have no access to.
    weekly_delivery = get_object_or_404(_available_weekly_deliveries(request.user), id=request.POST["weekly_delivery_id"])
    # Self-healing in lieu of a cron job: make sure the bookable window is filled
    # before we list the selectable dates for this delivery.
    weekly_delivery.ensure_delivery_dates()
    available_timespan_start, available_timespan_end = _get_start_end_command_period()
    selectable_delivery_dates = weekly_delivery.deliverydate_set.filter(active=True).filter(date__gte=available_timespan_start).filter(date__lte=available_timespan_end).order_by("date")
    order = None
    if request.POST["order_id"]:
        order = get_object_or_404(Order, id=request.POST["order_id"], customer=request.user)
    context = {"selectable_delivery_dates": selectable_delivery_dates, "strip_lines": request.POST["event_type"] == "change", "order": order}
    return render(request, "boulange/hx/available_dates.html", context=context)


@login_required
def hx_order_line(request):
    weekly_delivery = get_object_or_404(_available_weekly_deliveries(request.user), id=request.POST["weekly_delivery_id"])
    context = {"products": weekly_delivery.get_available_products()}
    return render(request, "boulange/hx/order_line.html", context=context)


@login_required
def hx_order_line_sum(request):
    index = int(request.POST["index"])
    product = get_object_or_404(Product, id=int(request.POST.getlist("product_id")[index]))
    try:
        product_qty = int(request.POST.getlist("product_qty")[index])
    except ValueError:
        product_qty = 0
    return HttpResponse(product.price * product_qty)


@login_required
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer != request.user or order.validated or order.checkout:
        raise PermissionDenied
    order.delete()
    return redirect("boulange:orders")


@login_required
def validate_orders(request, payment=False):
    available_timespan_start, available_timespan_end = _get_start_end_command_period()
    orders = (
        Order.objects.filter(customer=request.user)
        .filter(validated=False)
        .filter(delivery_date__date__gte=available_timespan_start)
        .filter(delivery_date__date__lte=available_timespan_end)
        .filter(delivery_date__weekly_delivery__online_payment=payment)
    )
    if not payment:
        for o in orders:
            o.validated = True
            o.save()
        return redirect("boulange:orders")
    checkout_price = 0
    for o in orders:
        checkout_price += o.total_price
    checkout = Checkout(remote_id="to be defined", customer=request.user)
    checkout.save()
    response = requests.post(
        settings.SUMUP_CHECKOUTS_URL,
        headers={"Authorization": f"Bearer {settings.SUMUP_API_KEY}"},
        json={
            "checkout_reference": checkout.id,
            "amount": float(checkout_price),
            "currency": "EUR",
            "merchant_code": settings.SUMUP_MERCHANT_CODE,
            "description": f"Paiement n°{checkout.id} sur boulange.lafermebioduresto.bzh",
        },
    )
    response.raise_for_status()
    checkout.remote_id = response.json()["id"]
    checkout.save()
    for o in orders:
        o.checkout = checkout
        o.save()
    return redirect("boulange:payment", checkout_id=checkout.id)


@login_required
def validate_cart(request):
    return validate_orders(request, payment=True)


def _sumup_checkout_data(checkout):
    response = requests.get(f"{settings.SUMUP_CHECKOUTS_URL}/{checkout.remote_id}", headers={"Authorization": f"Bearer {settings.SUMUP_API_KEY}"})
    response.raise_for_status()
    return response.json()


def _mark_checkout_paid(checkout, request):
    """Validate the orders of a paid checkout and notify the customer, exactly once.

    Returns whether this call is the one that validated them, so a reload of finalize()
    (or a later reconciliation pass) doesn't send the confirmation email a second time.
    """
    pending_orders = checkout.order_set.filter(validated=False)
    if not pending_orders.exists():
        return False
    pending_orders.update(validated=True)
    send_mail(
        "Boulangerie de la Ferme du Resto : commande validée",
        f"""Bonjour,\n
Votre commande a été validée. Retrouvez le détail de vos paiements ici : {request.build_absolute_uri(reverse('boulange:checkouts'))}
Merci et à bientôt !\n\n
            """,
        "boulangerie@lafermebioduresto.bzh",
        [checkout.customer.email],
        fail_silently=False,
    )
    return True


def reconcile_pending_checkouts(request, horizon_days=7):
    """Pick up payments that the customer's browser never confirmed.

    Confirmation normally happens because SumUp's widget redirects to finalize(), so a
    customer who pays and then closes the tab leaves a paid checkout whose orders stay
    unvalidated and invisible to the bakery. Rather than a cron job (same reasoning as
    ensure_delivery_dates) the baker's own daily screen re-asks SumUp about the few
    checkouts still pending on a recent or upcoming delivery. Reconciliation must never
    take that page down, so errors are swallowed per checkout.
    """
    pending_checkouts = Checkout.objects.filter(order__validated=False, order__delivery_date__date__gte=date.today() - timedelta(days=horizon_days)).distinct()
    reconciled = []
    for checkout in pending_checkouts:
        try:
            paid = _sumup_checkout_data(checkout)["status"] == "PAID"
        except (requests.RequestException, ValueError, KeyError):
            continue
        if paid and _mark_checkout_paid(checkout, request):
            reconciled.append(checkout)
    return reconciled


@login_required
def payment(request, checkout_id):
    checkout = get_object_or_404(Checkout, id=checkout_id)
    if checkout.customer != request.user:
        raise PermissionDenied
    if _sumup_checkout_data(checkout)["status"] == "PAID":
        return finalize(request, checkout_id)
    return render(request, "boulange/payment.html", context={"checkout": checkout, "email": request.user.email})


@login_required
def finalize(request, checkout_id):
    checkout = get_object_or_404(Checkout, id=checkout_id)
    if checkout.customer != request.user:
        raise PermissionDenied
    checkout_data = _sumup_checkout_data(checkout)
    # response = requests.get(f"{settings.SUMUP_RECEIPTS_URL}/{checkout_data['transaction_code']}",
    #                         params={"mid": settings.SUMUP_MERCHANT_CODE},
    #                         headers={"Authorization": f"Bearer {settings.SUMUP_API_KEY}"})
    # response.raise_for_status()
    # receipt_data = response.json()
    # print(receipt_data)
    if checkout_data["status"] != "PAID":
        return redirect("boulange:orders")
    _mark_checkout_paid(checkout, request)
    return render(request, "boulange/thanks.html")


@login_required
def cancel_checkout(request):
    checkout = get_object_or_404(Checkout, id=request.POST["checkout_id"])
    if checkout.customer != request.user:
        raise PermissionDenied
    # Ask SumUp first and only forget the checkout once it has actually been
    # cancelled there. Deleting locally up front would lose the payment record of an
    # already-paid checkout while silently returning its orders to the cart.
    response = requests.delete(f"{settings.SUMUP_CHECKOUTS_URL}/{checkout.remote_id}", headers={"Authorization": f"Bearer {settings.SUMUP_API_KEY}"})
    if not response.ok:
        # Typically a checkout that has already been paid: send the customer back to
        # the payment page, which re-reads the status and finalizes it.
        return redirect("boulange:payment", checkout_id=checkout.id)
    checkout.delete()
    return redirect("boulange:orders")


@login_required
def checkouts(request):
    checkouts = Checkout.objects.filter(customer=request.user).order_by("-id")
    return render(request, "boulange/checkouts.html", context={"checkouts": checkouts})


VALIDATED_ORDERS_PER_PAGE = 12


@login_required
@transaction.atomic
def orders(request, order_id=None, edit=False, duplicate=False):
    if request.POST:
        order = None
        if request.POST.get("order_id"):
            # editing existing order
            order = get_object_or_404(Order, id=int(request.POST["order_id"]))
            if order.validated or order.customer != request.user or order.checkout:
                raise PermissionDenied
        delivery_date, lines = _validate_order_submission(
            request.user,
            request.POST.get("delivery_date"),
            request.POST.getlist("product_id"),
            request.POST.getlist("product_qty"),
        )
        if not lines:
            # An order without a single line is not an order: editing everything down
            # to zero deletes it instead of leaving an empty 0 € order in the cart.
            if order is not None:
                order.delete()
            return redirect("boulange:orders")
        if order is None:
            order = Order(customer=request.user, validated=False)
        order.delivery_date = delivery_date
        order.notes = request.POST.get("notes", "")
        order.save()
        order.lines.all().delete()
        for product, quantity in lines:
            OrderLine.objects.create(order=order, product=product, quantity=quantity)
        return redirect("boulange:orders")
    order = None
    weekly_delivery = None
    if order_id:
        order = get_object_or_404(Order, id=order_id)
        if order.customer != request.user:
            raise PermissionDenied
        weekly_delivery = order.delivery_date.weekly_delivery
        if edit:
            if order.validated:
                raise PermissionDenied
            order_id = order.id
        if duplicate:
            order_id = False
    available_weekly_deliveries = _available_weekly_deliveries(request.user)
    if weekly_delivery is None:
        last_order = request.user.order_set.select_related("delivery_date__weekly_delivery").order_by("-id").first()
        if last_order is not None:
            weekly_delivery = last_order.delivery_date.weekly_delivery
    products = None
    if order:
        products = weekly_delivery.get_available_products()
    # Every card renders its delivery point, its lines and its total, so fetch those
    # up front rather than letting the template emit a query per order and per line.
    customer_orders = Order.objects.filter(customer=request.user).select_related("customer", "delivery_date__weekly_delivery__customer").prefetch_related("lines__product").order_by("-id")
    cart, to_validate = [], []
    for o in customer_orders.filter(validated=False):
        if o.checkout_id:
            return redirect("boulange:payment", checkout_id=o.checkout_id)
        if o.delivery_date.weekly_delivery.online_payment:
            cart.append(o)
        else:
            to_validate.append(o)
    # Validated orders are a history that only ever grows, so page through them instead
    # of rendering every order the customer has ever placed on every visit.
    validated_orders = Paginator(customer_orders.filter(validated=True), VALIDATED_ORDERS_PER_PAGE).get_page(request.GET.get("page"))

    context = {
        "validated_orders": validated_orders,
        "cart": cart,
        "to_validate": to_validate,
        "order": order,
        "order_id": order_id,
        "weekly_delivery": weekly_delivery,
        "available_weekly_deliveries": available_weekly_deliveries,
        "products": products,
    }
    return render(request, "boulange/orders.html", context=context)


@staff_required
def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


@staff_required
def actions(request, year=None, month=None, day=None, to_print=False, section=None):
    if not (year and month and day):
        target_date = date.today()
    else:
        target_date = date(year, month, day)
    reconcile_pending_checkouts(request)
    date_nav = []
    for i in range(-5, 6):
        date_nav.append(target_date + timedelta(days=i))
    context = {"actions": _get_actions(target_date), "target_date": target_date, "date_nav": date_nav, "to_print": to_print, "section": section}
    return render(request, "boulange/actions.html", context)


FRENCH_MONTHS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
MONTH_ABBR = ["", "Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]


def _int_param(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _stats_period(request):
    """Resolve a [start, end) window and a label from GET params.

    Precedence: custom range (start & end) > month > quarter > year (default current year).
    """
    year = _int_param(request.GET.get("year"), date.today().year)
    quarter = _int_param(request.GET.get("quarter"))
    month = _int_param(request.GET.get("month"))
    custom_start = _parse_iso_date(request.GET.get("start"))
    custom_end = _parse_iso_date(request.GET.get("end"))

    base = {"year": year, "quarter": None, "month": None, "custom_start": "", "custom_end": ""}
    if custom_start and custom_end:
        if custom_start > custom_end:
            custom_start, custom_end = custom_end, custom_start
        return {
            **base,
            "granularity": "custom",
            "start": custom_start,
            "end": custom_end + timedelta(days=1),  # end is inclusive for the user
            "label": f"Du {custom_start:%d/%m/%Y} au {custom_end:%d/%m/%Y}",
            "custom_start": custom_start.isoformat(),
            "custom_end": custom_end.isoformat(),
        }
    if month and 1 <= month <= 12:
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return {**base, "granularity": "month", "month": month, "start": start, "end": end, "label": f"{FRENCH_MONTHS[month]} {year}"}
    if quarter and 1 <= quarter <= 4:
        first_month = 3 * (quarter - 1) + 1
        start = date(year, first_month, 1)
        end = date(year + 1, 1, 1) if first_month + 3 > 12 else date(year, first_month + 3, 1)
        return {**base, "granularity": "quarter", "quarter": quarter, "start": start, "end": end, "label": f"T{quarter} {year}"}
    return {**base, "granularity": "year", "start": date(year, 1, 1), "end": date(year + 1, 1, 1), "label": str(year)}


@staff_required
def stats(request):
    period = _stats_period(request)
    lines = OrderLine.objects.filter(
        order__validated=True,
        order__delivery_date__date__gte=period["start"],
        order__delivery_date__date__lt=period["end"],
    ).select_related("product", "order", "order__customer")

    by_product = {}
    total_amount = Decimal(0)
    total_qty = 0
    order_ids = set()
    for line in lines:
        entry = by_product.setdefault(line.product, {"qty": 0, "amount": Decimal(0)})
        amount = line.get_price()
        entry["qty"] += line.quantity
        entry["amount"] += amount
        total_amount += amount
        total_qty += line.quantity
        order_ids.add(line.order_id)

    total_cost = Decimal(0)
    for product, entry in by_product.items():
        cost = product.cost_price * entry["qty"]
        entry["cost"] = cost
        entry["margin"] = entry["amount"] - cost
        entry["margin_pct"] = entry["margin"] / entry["amount"] * 100 if entry["amount"] else Decimal(0)
        total_cost += cost

    total_margin = total_amount - total_cost
    total_margin_pct = total_margin / total_amount * 100 if total_amount else Decimal(0)
    rows = sorted(by_product.items(), key=lambda item: item[1]["amount"], reverse=True)
    nb_orders = len(order_ids)
    avg_order = total_amount / nb_orders if nb_orders else Decimal(0)
    context = {
        "rows": rows,
        "total_amount": total_amount,
        "total_cost": total_cost,
        "total_margin": total_margin,
        "total_margin_pct": total_margin_pct,
        "total_qty": total_qty,
        "nb_orders": nb_orders,
        "avg_order": avg_order,
        "year": period["year"],
        "quarter": period["quarter"],
        "month": period["month"],
        "granularity": period["granularity"],
        "period_label": period["label"],
        "prev_year": period["year"] - 1,
        "next_year": period["year"] + 1,
        "quarters": [1, 2, 3, 4],
        "months": [(i, MONTH_ABBR[i]) for i in range(1, 13)],
        "custom_start": period["custom_start"],
        "custom_end": period["custom_end"],
    }
    return render(request, "boulange/stats.html", context)


@staff_required
def check_delivery_dates_consistency(request):
    delivery_dates = DeliveryDate.objects.select_related("weekly_delivery").prefetch_related("order_set")
    dds_by_weeklydelivery_and_date = defaultdict(list)
    annoying = {}
    for dd in delivery_dates:
        dds_by_weeklydelivery_and_date[(dd.weekly_delivery.id, dd.date)].append(dd)
        # delete empty deliverydates that have been generated on wrong weekday
        if dd.date.weekday() != dd.weekly_delivery.day_of_week:
            if dd.order_set.count() == 0:
                dd.delete()
            else:
                if "wrong_dow" not in annoying:
                    annoying["wrong_dow"] = []
                annoying["wrong_dow"].append(dd)
    for key, dds in dds_by_weeklydelivery_and_date.items():
        if len(dds) > 1:
            annoying[key] = dds
    context = {"annoying_dds": annoying}
    return render(request, "boulange/check_delivery_dates_consistency.html", context)


@login_required
def delivery_receipt(request, delivery_date_id=None, filter_on_user=False):
    delivery_date = get_object_or_404(DeliveryDate, id=delivery_date_id)
    orders = delivery_date.order_set.filter(validated=True).select_related("customer").prefetch_related("lines__product")
    if filter_on_user or not request.user.is_staff:
        orders = orders.filter(customer=request.user)
    context = {"delivery_date": delivery_date, "orders": orders}
    return render(request, "boulange/delivery_receipt.html", context)
