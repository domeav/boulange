from django.urls import include, path
from rest_framework import routers

from . import views

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
