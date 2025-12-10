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
    path("account_init", views.account_init, name="account_init"),
    path("reset_password/<token>", views.reset_password, name="reset_password"),
    path("hx/get_dates_for_weekly_delivery/", views.hx_get_dates_for_weekly_delivery, name="hx_get_dates_for_weekly_delivery"),
    path("hx/order_line/", views.hx_order_line, name="hx_order_line"),
    path("hx/order_line_sum/", views.hx_order_line_sum, name="hx_order_line_sum"),
    path("delete_order/<int:order_id>", views.delete_order, name="delete_order"),
    path("validate_cart/", views.validate_cart, name="validate_cart"),
    path("validate_orders/", views.validate_orders, name="validate_orders"),
    path("orders/<int:order_id>/duplicate", views.orders, name="orders", kwargs={"duplicate": True}),
    path("orders/<int:order_id>/edit", views.orders, name="orders", kwargs={"edit": True}),
    path("orders/", views.orders, name="orders"),
    path("checkouts/", views.checkouts, name="checkouts"),
    path("payment/<checkout_id>/", views.payment, name="payment"),
    path("cancel_checkout/", views.cancel_checkout, name="cancel_checkout"),
    path("finalize/<checkout_id>/", views.finalize, name="finalize"),
    path("products/", views.products, name="products"),
    path("actions/<int:year>/<int:month>/<int:day>/", views.actions, name="actions", kwargs={"to_print": False}),
    path("actions_print/<section>/<int:year>/<int:month>/<int:day>/", views.actions, name="actions_print", kwargs={"to_print": True}),
    path("actions/", views.actions, name="actions"),
    path("check_delivery_dates_consistency/", views.check_delivery_dates_consistency, name="check_delivery_dates_consistency"),
    path(
        "delivery_receipt/<int:delivery_date_id>/",
        views.delivery_receipt,
        name="delivery_receipt",
    ),
    path("user_delivery_receipt/<int:delivery_date_id>/", views.delivery_receipt, name="user_delivery_receipt", kwargs={"filter_on_user": True}),
    path("api/", include(router.urls)),
    path(
        "api/generate_delivery_dates/",
        views.generate_delivery_dates,
        name="generate_delivery_dates",
    ),
    path(
        "api/actions/<int:year>-<int:month>-<int:day>/",
        views.get_actions,
        name="get_actions",
    ),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
