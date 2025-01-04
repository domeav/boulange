from django.urls import path

from . import views

app_name = "boulange"
urlpatterns = [
    path("", views.index, name="index"),
    path("products", views.products, name="products"),
    path("actions/<int:year>/<int:month>/<int:day>", views.actions, name="actions"),
    path("actions", views.actions, name="actions"),
    path("orders/<int:year>/<int:month>/<int:day>/<span>", views.orders, name="orders"),
    path("orders", views.orders, name="orders"),
    path("orders", views.orders, name="orders"),
    path("receipt/<int:order_id>", views.receipt, name="receipt"),
    path(
        "monthly_receipt/<int:customer_id>/<int:year>/<int:month>",
        views.monthly_receipt,
        name="monthly_receipt",
    ),
    path(
        "generate_delivery_dates",
        views.generate_delivery_dates,
        name="generate_delivery_dates",
    ),
]
