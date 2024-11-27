from datetime import date, datetime, timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .DailyBatches import DailyBatches
from .models import DeliveryDate, Order, Product
from .forms import DateForm


def index(request):
    return render(request, "boulange/index.html")


def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


def orders(request):
    delivery_dates = (
        DeliveryDate.objects.order_by("delivery_point").order_by("date").all()
    )
    context = {"delivery_dates": delivery_dates}
    return render(request, "boulange/orders.html", context)


def receipt(request, order_id):
    context = {"orders": [get_object_or_404(Order, id=order_id)], "monthly": False}
    return render(request, "boulange/receipt.html", context)


def monthly_receipt(request, customer_id, year, month):
    start = date(year, month, 1)
    end = date(year, month + 1 if month < 12 else 1, 1)
    orders = (
        Order.objects.filter(customer__id=customer_id)
        .filter(delivery_date__date__gte=start)
        .filter(delivery_date__date__lt=end)
    )
    context = {
        "orders": orders,
        "monthly": True,
        "total": sum([o.get_total_price() for o in orders]),
    }
    return render(request, "boulange/receipt.html", context)


def actions(request, year=None, month=None, day=None):
    if request.method == "POST":
        form = DateForm(request.POST)
        if form.is_valid():
            when = form.cleaned_data["date"]
            return redirect("boulange:actions", when.year, when.month, when.day)
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
        "form": DateForm(initial={"date": target_date}),
    }
    return render(request, "boulange/actions.html", context)
