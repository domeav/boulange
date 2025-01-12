from datetime import date, timedelta

from django_filters import rest_framework as filters
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view
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

### REST FRAMEWORK

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
    queryset = DeliveryDate.objects.all().order_by("id")
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


@api_view(["GET"])
def get_actions(request, year, month, day):
    target_date = date(year, month, day)
    delivery_dates = (
        DeliveryDate.objects.filter(date__gte=target_date)
        .filter(active=True)
        .filter(date__lte=target_date + timedelta(days=2))
        .all()
    )
    actions = None
    for delivery_date in delivery_dates:
        for order in delivery_date.order_set.all():
            actions = order.get_actions(target_date, actions)

    return Response(actions)

### REGULAR VIEWS

def index(request):
    return render(request, "boulange/index.html")

@login_required
def my_orders(request):
    context = { "orders": Order.objects.filter(customer=request.user) }
    return render(request, "boulange/my_orders.html", context)

def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)

def orders_by_customer(request):
    context = {}
    return render(request, "boulange/orders.html", context)

def actions(request, year=None, month=None, day=None):
    context = {}
    return render(request, "boulange/actions.html", context)
