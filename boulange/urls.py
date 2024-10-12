from django.urls import path

from . import views

app_name = "boulange"
urlpatterns = [
    path("", views.index, name="index"),
    path("products", views.products, name="products"),
    path("actions/<int:year>/<int:month>/<int:day>", views.actions, name="actions"),
    path("actions", views.actions, name="actions"),
    path("orders", views.orders, name="orders"),
    path("invoice/<int:order_id>", views.invoice, name="invoice"),
    path(
        "monthly_invoice/<int:customer_id>/<int:year>/<int:month>",
        views.monthly_invoice,
        name="monthly_invoice",
    ),
]
