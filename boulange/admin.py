import nested_admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from datetime import date


from .models import (
    Customer,
    DeliveryDay,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
)


class DeliveryDateAdmin(admin.ModelAdmin):
    list_display = ("delivery_day", "date")


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    fieldsets = [
        (
            "Professional",
            {
                "classes": ["collapse"],
                "fields": ["is_professional", "pro_discount_percentage"],
            },
        )
    ]


class DeliveryDayAdmin(admin.ModelAdmin):
    model = DeliveryDay


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


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 3
    autocomplete_fields = ["product"]


class OrderAdmin(admin.ModelAdmin):
    list_display = ("customer", "delivery_date")
    model = Order
    inlines = [OrderLineInline]
    save_as = True


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(DeliveryDay, DeliveryDayAdmin)
admin.site.register(DeliveryDate, DeliveryDateAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)
