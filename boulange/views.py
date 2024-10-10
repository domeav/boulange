from datetime import date, datetime, timedelta
from itertools import chain

from django.http import HttpResponse
from django.shortcuts import render, redirect

from .DailyBatches import DailyBatches
from .models import DeliveryDate, Order, Product


def index(request):
    return HttpResponse("Hello, world.")


def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


def orders(request):
    delivery_dates = DeliveryDate.objects.filter(date__gte=datetime.now()).order_by("delivery_point").all()
    context = {"delivery_dates": delivery_dates}
    return render(request, "boulange/orders.html", context)


def actions(request, year=None, month=None, day=None):
    if not (year and month and day):
        today = datetime.now()
        return redirect('boulange:actions', today.year, today.month, today.day)
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
