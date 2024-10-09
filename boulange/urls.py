from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("products", views.products, name="products"),
    path("actions/<int:year>/<int:month>/<int:day>", views.actions, name="actions"),
    path("orders", views.orders, name="orders"),
]
