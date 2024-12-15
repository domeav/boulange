import nested_admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.forms import BaseInlineFormSet
from datetime import date


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


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [CustomerInline]


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
    extra = 1


class DeliveryPointAdmin(admin.ModelAdmin):
    list_display = ("name", "batch_target", "active")
    inlines = [DeliveryDateInline]


class OrderLineInline(nested_admin.NestedTabularInline):
    model = OrderLine
    extra = 3
    autocomplete_fields = ["product"]


class OrderAdmin(nested_admin.NestedModelAdmin):
    list_display = ("customer", "delivery_date")
    model = Order
    inlines = [OrderLineInline]
    save_as = True


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(DeliveryPoint, DeliveryPointAdmin)
admin.site.register(Order, OrderAdmin)
