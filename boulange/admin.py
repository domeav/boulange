import nested_admin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from datetime import date


from .models import (
    Customer,
    WeeklyDelivery,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
)


class DeliveryDateAdmin(admin.ModelAdmin):
    list_display = ("weekly_delivery", "date", "active")
    search_fields = [
        "weekly_delivery__user__first_name",
        "weekly_delivery__user__last_name",
        "weekly_delivery__user__username",
    ]


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    fieldsets = [
        (None,
          {"fields": ['address']}),
        (
            "Professional",
            {
                "classes": ["collapse"],
                "fields": ["is_professional", "pro_discount_percentage"],
            },
        )
    ]


@admin.action(description="Generate delivery dates for one year")
def generate_delivery_dates(modeladmin, request, queryset):
    for weekly_delivery in queryset:
        weekly_delivery.generate_delivery_dates()


class WeeklyDeliveryAdmin(admin.ModelAdmin):
    model = WeeklyDelivery
    actions = [generate_delivery_dates]
    search_fields = ["user__first_name", "user__last_name", "user__username"]


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
    autocomplete_fields = ["delivery_date"]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(WeeklyDelivery, WeeklyDeliveryAdmin)
admin.site.register(DeliveryDate, DeliveryDateAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)
