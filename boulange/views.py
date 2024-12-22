from datetime import date, datetime, timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .DailyBatches import DailyBatches
from .models import DeliveryDate, Order, Product, DeliveryDay
from .forms import DateForm


def index(request):
    return render(request, "boulange/index.html")


def products(request):
    context = {"products": Product.objects.all()}
    return render(request, "boulange/products.html", context)


def orders(request, year=None, month=None, day=None, span="week"):
    if request.method == "POST":
        form = DateForm(request.POST)
        if form.is_valid():
            when = form.cleaned_data["date"]
            span = form.data.get("span", span)
            return redirect("boulange:orders", when.year, when.month, when.day, span)
    if not (year and month and day):
        today = date.today()
        return redirect("boulange:orders", today.year, today.month, today.day, span)
    delivery_dates = DeliveryDate.objects.order_by("delivery_day__user").order_by(
        "date"
    )
    target = date(year, month, day)
    if span == "day":
        start, end = target, target + timedelta(days=1)
    if span == "week":
        start = target - timedelta(days=target.weekday())
        end = start + timedelta(days=7)
    if span == "month":
        start = date(target.year, target.month, 1)
        try:
            end = date(target.year, target.month + 1, 1)
        except ValueError:
            end = date(target.year + 1, 1, 1)
    if span == "year":
        start = date(target.year, 1, 1)
        end = date(target.year + 1, 1, 1)
    delivery_dates = delivery_dates.filter(date__gte=start).filter(date__lt=end)
    context = {
        "delivery_dates": delivery_dates,
        "form": DateForm(initial={"date": target}),
    }
    return render(request, "boulange/orders.html", context)


def receipt(request, order_id):
    context = {"orders": [get_object_or_404(Order, id=order_id)], "monthly": False}
    return render(request, "boulange/receipt.html", context)


def monthly_receipt(request, customer_id, year, month):
    start = date(year, month, 1)
    try:
        end = date(year, month + 1, 1)
    except ValueError:
        end = date(year + 1, 1, 1)
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
            delivery_date.delivery_day.batch_target == "SAME_DAY"
            and delivery_date.date == target_date
        ) or (
            delivery_date.delivery_day.batch_target == "PREVIOUS_DAY"
            and delivery_date.date == target_date + timedelta(days=1)
        ):
            for order in delivery_date.order_set.all():
                for line in order.orderline_set.all():
                    daily_batches.add(line, delivery_date.delivery_day)
        elif (
            delivery_date.delivery_day.batch_target == "SAME_DAY"
            and delivery_date.date == target_date + timedelta(days=1)
        ) or (
            delivery_date.delivery_day.batch_target == "PREVIOUS_DAY"
            and delivery_date.date == target_date + timedelta(days=2)
        ):
            for order in delivery_date.order_set.all():
                for line in order.orderline_set.all():
                    preparations_batches.add(line, delivery_date.delivery_day)
    context = {
        "target_date": target_date,
        "daily_batches": daily_batches,
        "previous": target_date - timedelta(days=1),
        "next": target_date + timedelta(days=1),
        "preparations_batches": preparations_batches,
        "form": DateForm(initial={"date": target_date}),
    }
    return render(request, "boulange/actions.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def generate_delivery_dates(request):
    for dday in DeliveryDay.objects.all():
        dday.generate_delivery_dates()
    return HttpResponse("Delivery dates generated!")
