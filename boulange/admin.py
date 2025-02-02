from django.contrib import admin
from django.contrib.auth.models import Group

from .models import (
    Customer,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ProductLine,
    WeeklyDelivery,
)

admin.site.unregister(Group)


class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "per_unit_price")


class ProductLineInline(admin.TabularInline):
    model = ProductLine
    extra = 1


class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "ref", "price", "active")
    inlines = [ProductLineInline]
    search_fields = ["ref", "name"]


admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)


class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "display_name",
        "email",
        "is_professional",
        "pro_discount_percentage",
        "address",
    )
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "username",
                    "display_name",
                    "email",
                    "is_professional",
                    "pro_discount_percentage",
                    "address",
                ]
            },
        ),
        ("Utilisateur", {"fields": ["is_staff", "is_superuser", "is_active"]}),
    ]


admin.site.register(Customer, CustomerAdmin)


@admin.action(description="Generate delivery dates for one year")
def generate_delivery_dates(modeladmin, request, queryset):
    for weekly_delivery in queryset:
        weekly_delivery.generate_delivery_dates()


class WeeklyDeliveryAdmin(admin.ModelAdmin):
    model = WeeklyDelivery
    actions = [generate_delivery_dates]
    search_fields = ["customer__display_name", "customer__username", "day_of_week"]


class DeliveryDateAdmin(admin.ModelAdmin):
    list_display = ("weekly_delivery", "date", "active")
    search_fields = [
        "weekly_delivery__customer__display_name",
        "weekly_delivery__customer__username",
        "date",
    ]


admin.site.register(WeeklyDelivery, WeeklyDeliveryAdmin)
admin.site.register(DeliveryDate, DeliveryDateAdmin)


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


admin.site.register(Order, OrderAdmin)
