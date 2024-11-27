import nested_admin
from django.contrib import admin

from .models import (
    Customer,
    DeliveryDate,
    DeliveryPoint,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
)


class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "active",
        "is_professional",
        "pro_discount_percentage",
    )


class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "per_unit_price")


class ProductLineInline(admin.TabularInline):
    model = ProductLine
    extra = 1


class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "ref", "price", "active")
    inlines = [ProductLineInline]
    search_fields = ["ref", "name"]


class DeliveryDateInline(admin.StackedInline):
    model = DeliveryDate
    extra = 4


class DeliveryPointAdmin(admin.ModelAdmin):
    list_display = ("name", "batch_target", "active")
    inlines = [DeliveryDateInline]


class OrderLineInline(nested_admin.NestedTabularInline):
    model = OrderLine
    extra = 3
    autocomplete_fields = ["product"]


class OrderInline(nested_admin.NestedTabularInline):
    model = Order
    inlines = [OrderLineInline]


class OrderAdmin(nested_admin.NestedModelAdmin):
    list_display = ("customer", "delivery_date")
    model = Order
    inlines = [OrderLineInline]
    save_as = True


class DeliveryDateAdmin(nested_admin.NestedModelAdmin):
    list_display = ("delivery_point", "date")
    inlines = [OrderInline]
    save_as = True


admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(DeliveryPoint, DeliveryPointAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(DeliveryDate, DeliveryDateAdmin)
admin.site.register(Order, OrderAdmin)
