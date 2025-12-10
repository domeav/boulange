from datetime import date, timedelta

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
    Settings,
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
    search_fields = ["ref"]
    save_as = True


admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)


class CustomerAdmin(admin.ModelAdmin):
    list_filter = ("is_professional",)
    list_display = ("username", "display_name", "email", "is_professional", "pro_discount_percentage", "address")
    search_fields = ["username", "email"]
    fieldsets = [
        (
            None,
            {"fields": ["username", "display_name", "email", "is_professional", "pro_discount_percentage", "address", "notes"]},
        ),
        ("Utilisateur", {"fields": ["is_staff", "is_superuser", "is_active"]}),
    ]


admin.site.register(Customer, CustomerAdmin)


@admin.action(description="Generate delivery dates for one year")
def generate_delivery_dates(modeladmin, request, queryset):
    for weekly_delivery in queryset:
        weekly_delivery.generate_delivery_dates()


class WeeklyDeliveryAdmin(admin.ModelAdmin):
    list_display = ("customer", "day_of_week", "active", "public_delivery_point", "online_payment")
    list_filter = ("active", "day_of_week")
    filter_horizontal = ("allowed_customers",)
    model = WeeklyDelivery
    actions = [generate_delivery_dates]
    search_fields = ["customer__display_name", "customer__username", "day_of_week"]
    save_as = True


class MyDateFilter(admin.DateFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        newlinks = []
        for linkname, linkinfo in self.links:
            if linkname != "Les 7 derniers jours":
                newlinks.append((linkname, linkinfo))
        self.links = newlinks
        self.links.insert(2, ("Aujourd'hui et après", {"date__gte": date.today() + timedelta(days=1), "date__lt": date.today() + timedelta(days=365)}))
        self.links.insert(2, ("Demain", {"date__gte": date.today() + timedelta(days=1), "date__lt": date.today() + timedelta(days=2)}))


@admin.action(description="Duplicate commands from the older selected deliverydate to the newer ones, by weeklydelivery")
def duplicate_delivery_date_commands(modeladmin, request, queryset):
    original_delivery_dates = {}
    for delivery_date in queryset.order_by("date"):
        if delivery_date.weekly_delivery not in original_delivery_dates:
            original_delivery_dates[delivery_date.weekly_delivery] = delivery_date
        else:
            delivery_date.duplicate_commands_from(original_delivery_dates[delivery_date.weekly_delivery])


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    fields = ["customer", "total_price"]
    readonly_fields = ["customer", "total_price"]
    can_delete = True
    show_change_link = True


class DeliveryDateAdmin(admin.ModelAdmin):
    list_display = ("weekly_delivery", "date", "active")
    list_filter = ("active", ("date", MyDateFilter), "weekly_delivery__day_of_week", "weekly_delivery")
    readonly_fields = ("date", "weekly_delivery")
    inlines = [OrderInline]
    search_fields = [
        "weekly_delivery__customer__display_name",
        "weekly_delivery__customer__username",
        "date",
    ]
    actions = [duplicate_delivery_date_commands]

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if "/autocomplete/" in request.path:
            return queryset.filter(date__gte=date.today()).filter(active=True), may_have_duplicates
        return queryset, may_have_duplicates

    def has_add_permission(self, request):
        return False


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
    list_filter = [("delivery_date__date", MyDateFilter), "customer__display_name"]


admin.site.register(Order, OrderAdmin)


class SettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "value")
    search_fields = ["name"]
    save_as = True


admin.site.register(Settings, SettingsAdmin)
