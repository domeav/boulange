from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .forms import OrderForm, OrderLineFormSet
from .models import (
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

TZ = ZoneInfo("Europe/Paris")

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
def generate_delivery_dates(request):
    for dday in WeeklyDelivery.objects.all():
        dday.generate_delivery_dates()
    return Response({"message": "Delivery dates generated!"})


def _get_actions(target_date):
    delivery_dates = DeliveryDate.objects.filter(date__gte=target_date).filter(active=True).filter(date__lte=target_date + timedelta(days=2)).all()
    actions = None
    for delivery_date in delivery_dates:
        for order in delivery_date.order_set.filter(validated=True).all():
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
    if not request.POST["email"]:
        return redirect("boulange:index")
    customer = get_object_or_404(Customer, email=request.POST["email"])
    token = ResetAccountToken(customer=customer)
    send_mail(
        "Boulangerie de la Ferme du Resto : initialisation de votre compte",
        f"Bonjour,\n\nRendez-vous à l'adresse suivante pour positionner le mot de passe de votre compte :\n\n{request.build_absolute_uri('/reset_password/'+str(token.token))}\n\nCe lien est valable 24h\n\nAttention : votre identifiant pour l'accès au service est : {customer.username}",
        "boulangerie@lafermebioduresto.bzh",
        ["dom.eav@franceimpro.net"],
        fail_silently=False,
    )
    token.save()
    return render(request, "registration/account_init.html")


def reset_password(request, token):
    token = get_object_or_404(ResetAccountToken, token=token)
    if request.POST:
        if len(request.POST["newpw"]) < 8:
            return redirect("boulange:reset_password", token=token.token)
        else:
            token.customer.set_password(request.POST["newpw"])
            token.customer.save()
            token.delete()
            return redirect("boulange:index")

    if (datetime.now(TZ) - token.created) > timedelta(days=1):
        return HttpResponse("Ce lien n'est plus valide")
    context = {"token": token}
    return render(request, "registration/reset_password.html", context=context)


def _get_start_end_command_period():
    available_timespan_start = date.today() + timedelta(days=2)
    available_timespan_end = date.today() + timedelta(days=56)
    return available_timespan_start, available_timespan_end


def hx_get_dates_for_weekly_delivery(request):
    weekly_delivery = WeeklyDelivery.objects.get(id=request.POST["weekly_delivery_id"])
    available_timespan_start, available_timespan_end = _get_start_end_command_period()
    selectable_delivery_dates = weekly_delivery.deliverydate_set.filter(date__gte=available_timespan_start).filter(date__lte=available_timespan_end).order_by("date")
    context = {"selectable_delivery_dates": selectable_delivery_dates, "strip_lines": request.POST["event_type"] == "change"}
    return render(request, "boulange/hx/available_dates.html", context=context)


def hx_order_line(request):
    weekly_delivery = WeeklyDelivery.objects.get(id=request.POST["weekly_delivery_id"])
    context = {"products": weekly_delivery.get_available_products()}
    return render(request, "boulange/hx/order_line.html", context=context)


def hx_order_line_sum(request):
    index = int(request.POST["index"])
    product = Product.objects.get(id=int(request.POST.getlist("product_id")[index]))
    try:
        product_qty = int(request.POST.getlist("product_qty")[index])
    except ValueError:
        product_qty = 0
    return HttpResponse(product.price * product_qty)


@login_required
def delete_order(request, order_id):
    order = Order.objects.get(id=order_id)
    if order.customer != request.user or order.validated:
        raise PermissionDenied
    order.delete()
    return redirect("boulange:orders")


@login_required
def validate_cart(request):
    send_mail("Hello there", "Merci pour la commande !", "boulangerie@lafermebioduresto.bzh", ["dom.eav@franceimpro.net"], fail_silently=False)
    orders = Order.objects.filter(customer=request.user).filter(validated=False)
    for order in orders:
        order.validated = True
        order.save()
    return redirect("boulange:orders")


@login_required
@transaction.atomic
def orders(request, order_id=None, edit=False, duplicate=False):
    if request.POST:
        if request.POST["order_id"]:
            # editing existing order
            order = Order.objects.get(id=int(request.POST["order_id"]))
            if order.validated or order.customer != request.user:
                raise PermissionDenied
            order.delivery_date_id = int(request.POST["delivery_date"])
            order.notes = request.POST["notes"]
            for line in order.lines.all():
                line.delete()
        else:
            order = Order(customer=request.user, delivery_date_id=int(request.POST["delivery_date"]), notes=request.POST["notes"], validated=False)
        lines = []
        for product_id, qty in zip(request.POST.getlist("product_id"), request.POST.getlist("product_qty")):
            if qty:
                lines.append(OrderLine(order=order, product_id=product_id, quantity=int(qty)))
        if lines:
            order.save()
            for line in lines:
                line.save()
        return redirect("boulange:orders")
    order = None
    weekly_delivery = None
    if order_id:
        order = Order.objects.get(id=order_id)
        if order.customer != request.user:
            raise PermissionDenied
        weekly_delivery = order.delivery_date.weekly_delivery
        if edit:
            if order.validated:
                raise PermissionDenied
            order_id = order.id
        if duplicate:
            order_id = False
    selectable_delivery_dates = []
    if request.user.is_professional:
        available_weekly_deliveries = WeeklyDelivery.objects.filter(customer=request.user)
    else:
        available_weekly_deliveries = WeeklyDelivery.objects.filter(Q(public_delivery_point=True) | Q(id__in=request.user.private_weekly_deliveries.all()))
    if weekly_delivery == None and request.user.order_set.exists():
        weekly_delivery = request.user.order_set.order_by("-id").first().delivery_date.weekly_delivery
    products = None
    if order:
        products = weekly_delivery.get_available_products()
    validated_orders, cart = [], []
    for o in Order.objects.filter(customer=request.user).order_by("-id"):
        if o.validated:
            validated_orders.append(o)
        else:
            cart.append(o)

    context = {
        "validated_orders": validated_orders,
        "cart": cart,
        "order": order,
        "order_id": order_id,
        "weekly_delivery": weekly_delivery,
        "available_weekly_deliveries": available_weekly_deliveries,
        "products": products,
    }
    return render(request, "boulange/orders.html", context=context)


@login_required
def products(request):
    context = {"products": Product.objects.all().order_by("name")}
    return render(request, "boulange/products.html", context)


@login_required
def actions(request, year=None, month=None, day=None, to_print=False, section=None):
    if not (year and month and day):
        target_date = date.today()
    else:
        target_date = date(year, month, day)
    date_nav = []
    for i in range(-5, 6):
        date_nav.append(target_date + timedelta(days=i))
    context = {"actions": _get_actions(target_date), "target_date": target_date, "date_nav": date_nav, "to_print": to_print, "section": section}
    return render(request, "boulange/actions.html", context)


@login_required
def check_delivery_dates_consistency(request):
    delivery_dates = DeliveryDate.objects.all()
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
def delivery_receipt(request, delivery_date_id):
    context = {"delivery_date": DeliveryDate.objects.get(id=delivery_date_id)}
    return render(request, "boulange/delivery_receipt.html", context)
