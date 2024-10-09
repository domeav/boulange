from datetime import date, datetime, timedelta
from itertools import chain

from django.http import HttpResponse
from django.shortcuts import render

from .DailyBatches import DailyBatches
from .models import DeliveryDate, Order, Product


def index(request):
    return HttpResponse("Hello, world.")


def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


def orders(request):
    orders = Order.objects.filter(delivery_date__date__gte=datetime.now()).all()
    todo = set()
    for order in orders:
        operation_date = order.delivery_date.date
        print(order.delivery_date.delivery_point)
        if order.delivery_date.delivery_point.batch_target == "PREVIOUS_DAY":
            operation_date -= timedelta(days=1)
        todo.add(operation_date)
    context = {"orders": orders, "todo": sorted(todo)}
    return render(request, "boulange/orders.html", context)


def actions(request, year, month, day):
    target_date = date(year, month, day)
    deliveries_d0 = (
        DeliveryDate.objects.filter(date=target_date)
        .filter(delivery_point__batch_target="SAME_DAY")
        .all()
    )
    deliveries_d1 = (
        DeliveryDate.objects.filter(date=target_date + timedelta(days=1))
        .filter(delivery_point__batch_target="PREVIOUS_DAY")
        .all()
    )
    daily_batches = DailyBatches()
    for delivery_date in chain(deliveries_d0, deliveries_d1):
        for order in delivery_date.order_set.all():
            for line in order.orderline_set.all():
                daily_batches.add(line, delivery_date.delivery_point)
    context = {"target_date": target_date, "daily_batches": daily_batches}
    return render(request, "boulange/actions.html", context)
