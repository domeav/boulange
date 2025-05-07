from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import (
    Customer,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
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
        for order in delivery_date.order_set.all():
            actions = order.get_actions(target_date, actions)
    if actions:
        actions.finalize()
    return actions


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def get_actions(request, year, month, day):
    return Response(_get_actions(date(year, month, day)))


# REGULAR VIEWS


def index(request):
    return render(request, "boulange/index.html")


@login_required
def my_orders(request):
    context = {"orders": Order.objects.filter(customer=request.user).order_by("-id")}
    return render(request, "boulange/my_orders.html", context)


@login_required
def products(request):
    context = {"products": Product.objects.all().order_by("name")}
    return render(request, "boulange/products.html", context)


@login_required
def actions(request, year=None, month=None, day=None, to_print=False):
    if not (year and month and day):
        target_date = date.today()
    else:
        target_date = date(year, month, day)
    date_nav = []
    for i in range(-5, 6):
        date_nav.append(target_date + timedelta(days=i))
    context = {"actions": _get_actions(target_date), "target_date": target_date, "date_nav": date_nav, "to_print": to_print}
    return render(request, "boulange/actions.html", context)


@login_required
def check_delivery_dates_consistency(request):
    delivery_dates = DeliveryDate.objects.all()
    dds_by_weeklydelivery_and_date = defaultdict(list)
    for dd in delivery_dates:
        dds_by_weeklydelivery_and_date[(dd.weekly_delivery.id, dd.date)].append(dd)
    annoying = {}
    for key, dds in dds_by_weeklydelivery_and_date.items():
        if len(dds) > 1:
            annoying[key] = dds
    context = {"annoying_dds": annoying}
    return render(request, "boulange/check_delivery_dates_consistency.html", context)


@login_required
def delivery_receipt(request, delivery_date_id):
    context = {"delivery_date": DeliveryDate.objects.get(id=delivery_date_id)}
    return render(request, "boulange/delivery_receipt.html", context)
