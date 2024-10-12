from datetime import date, datetime, timedelta

from django.http import HttpResponse
from django.shortcuts import redirect, render

from .DailyBatches import DailyBatches
from .models import DeliveryDate, Order, Product


def index(request):
    return render(request, "boulange/index.html")


def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


def orders(request):
    delivery_dates = (
        DeliveryDate.objects.filter(date__gte=datetime.now())
        .order_by("delivery_point")
        .all()
    )
    context = {"delivery_dates": delivery_dates}
    return render(request, "boulange/orders.html", context)


def actions(request, year=None, month=None, day=None):
    if not (year and month and day):
        today = datetime.now()
        return redirect("boulange:actions", today.year, today.month, today.day)
    target_date = date(year, month, day)
    deliveries = (
        DeliveryDate.objects.filter(date__gte=target_date)
        .filter(date__lte=target_date + timedelta(days=2))
        .all()
    )
    daily_batches = DailyBatches()
    # levain+soaking
    preparations_batches = DailyBatches()
    for delivery_date in deliveries:
        if (
            delivery_date.delivery_point.batch_target == "SAME_DAY"
            and delivery_date.date == target_date
        ) or (
            delivery_date.delivery_point.batch_target == "PREVIOUS_DAY"
            and delivery_date.date == target_date + timedelta(days=1)
        ):
            for order in delivery_date.order_set.all():
                for line in order.orderline_set.all():
                    daily_batches.add(line, delivery_date.delivery_point)
        elif (
            delivery_date.delivery_point.batch_target == "SAME_DAY"
            and delivery_date.date == target_date + timedelta(days=1)
        ) or (
            delivery_date.delivery_point.batch_target == "PREVIOUS_DAY"
            and delivery_date.date == target_date + timedelta(days=2)
        ):
            for order in delivery_date.order_set.all():
                for line in order.orderline_set.all():
                    preparations_batches.add(line, delivery_date.delivery_point)
    context = {
        "target_date": target_date,
        "daily_batches": daily_batches,
        "previous": target_date - timedelta(days=1),
        "next": target_date + timedelta(days=1),
        "preparations_batches": preparations_batches,
    }
    return render(request, "boulange/actions.html", context)
