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


class ProductLineInline(admin.TabularInline):
    model = ProductLine
    extra = 1


class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductLineInline]


class DeliveryDateInline(admin.StackedInline):
    model = DeliveryDate
    extra = 4


class DeliveryPointAdmin(admin.ModelAdmin):
    inlines = [DeliveryDateInline]


class OrderLineInline(nested_admin.NestedTabularInline):
    model = OrderLine
    extra = 3


class OrderInline(nested_admin.NestedTabularInline):
    model = Order
    inlines = [OrderLineInline]


class OrderAdmin(admin.ModelAdmin):
    model = Order
    inlines = [OrderLineInline]
    save_as = True


class DeliveryDateAdmin(nested_admin.NestedModelAdmin):
    inlines = [OrderInline]
    save_as = True


admin.site.register(Ingredient)
admin.site.register(Product, ProductAdmin)
admin.site.register(DeliveryPoint, DeliveryPointAdmin)
admin.site.register(Customer)
admin.site.register(DeliveryDate, DeliveryDateAdmin)
admin.site.register(Order, OrderAdmin)
