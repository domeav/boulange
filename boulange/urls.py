from django.urls import include, path
from rest_framework import routers

from . import views

app_name = "boulange"

router = routers.DefaultRouter()
router.register(r"ingredients", views.IngredientViewSet)
router.register(r"products", views.ProductViewSet)
router.register(r"product_lines", views.ProductLineViewSet)
router.register(r"customers", views.CustomerViewSet)
router.register(r"weekly_deliveries", views.WeeklyDeliveryViewSet)
router.register(r"delivery_dates", views.DeliveryDateViewSet)
router.register(r"orders", views.OrderViewSet)
router.register(r"order_lines", views.OrderLineViewSet)

urlpatterns = [
    path("", views.index, name="index"),
    path("my_orders", views.my_orders, name="my_orders"),
    path("products", views.products, name="products"),
    path("actions/<int:year>/<int:month>/<int:day>", views.actions, name="actions"),
    path("actions", views.actions, name="actions"),
    path("orders/by_customer/", views.orders_by_customer, name="orders_by_customer"),
    path("api/", include(router.urls)),
    path(
        "api/generate_delivery_dates",
        views.generate_delivery_dates,
        name="generate_delivery_dates",
    ),
    path(
        "api/actions/<int:year>-<int:month>-<int:day>",
        views.get_actions,
        name="get_actions",
    ),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
