from django.shortcuts import render
from django.http import HttpResponse
from .models import Recipe, DeliveryDate
from datetime import date

def index(request):
    return HttpResponse("Hello, world.")


def recipes(request):
    context = {
        "recipes": Recipe.objects.all()
    }
    return render(request, "boulange/recipes.html", context)


def actions(request):
    target_date = date(2024, 9, 12)
    context = {
        "deliveries": DeliveryDate.objects.filter(date=target_date).all()
    }
    return render(request, "boulange/actions.html", context)
