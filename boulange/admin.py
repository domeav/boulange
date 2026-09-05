from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html

from boulange import SPECIAL_UNITS_WEIGHTS

from .models import (
    TVA,
    Checkout,
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


def _ingredient_weight_factors():
    """ingredient id -> grams per unit of quantity (None when the unit isn't weighable)."""
    factors = {}
    for ing in Ingredient.objects.all():
        if ing.unit == "g":
            factors[ing.id] = 1
        elif ing.unit in SPECIAL_UNITS_WEIGHTS:
            factors[ing.id] = SPECIAL_UNITS_WEIGHTS[ing.unit]
        else:
            factors[ing.id] = None
    return factors


def _product_raw_weights(factors):
    """product id -> grams of its own raw_ingredients (None if any ingredient isn't weighable).

    Used client-side to add the orig_product (base dough) contribution live.
    """
    weights = {}
    for product in Product.objects.prefetch_related("raw_ingredients__ingredient"):
        total = 0
        weighable = True
        for line in product.raw_ingredients.all():
            factor = factors.get(line.ingredient_id)
            if factor is None:
                weighable = False
                break
            total += line.quantity * factor
        weights[product.id] = total if weighable else None
    return weights


admin.site.unregister(Group)


class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "per_unit_price")


class ProductLineInline(admin.TabularInline):
    model = ProductLine
    extra = 1


def _recipe_dough_weight_text(obj):
    if obj is None or obj.pk is None:
        return "— (enregistrer pour calculer)"
    try:
        per_unit = obj.weight
    except ValueError:
        return "non calculable (ingrédient non pesable)"
    total = per_unit * obj.nb_units
    return f"{total:.0f} g (recette pour {obj.nb_units} u. — {per_unit:.0f} g/u.)"


class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "ref", "price", "display_priority", "active")
    inlines = [ProductLineInline]
    search_fields = ["ref", "name"]
    save_as = True

    class Media:
        js = ("boulange/admin_recipe_weight.js",)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        factors = _ingredient_weight_factors()
        extra_context = extra_context or {}
        extra_context["dough_ingredient_factors"] = factors
        extra_context["dough_product_raw_weights"] = _product_raw_weights(factors)
        obj = self.get_object(request, object_id) if object_id else None
        extra_context["dough_weight_initial"] = _recipe_dough_weight_text(obj)
        return super().changeform_view(request, object_id, form_url, extra_context)


admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Product, ProductAdmin)


class CustomerAdmin(admin.ModelAdmin):
    list_filter = ("is_professional",)
    list_display = ("username", "display_name", "email", "is_professional", "pro_discount_percentage", "address", "order_history")
    search_fields = ["display_name", "username", "email"]
    fieldsets = [
        (
            None,
            {"fields": ["username", "display_name", "email", "is_professional", "pro_discount_percentage", "address", "notes"]},
        ),
        ("Utilisateur", {"fields": ["is_staff", "is_superuser", "is_active"]}),
    ]

    @admin.display(description="Historique")
    def order_history(self, obj):
        return format_html('<a href="{}?customer={}">commandes</a>', reverse("boulange:customer_orders"), obj.id)


admin.site.register(Customer, CustomerAdmin)


@admin.action(description="Générer les dates de livraison pour un an")
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
        self.links.insert(2, ("Aujourd'hui et après", {self.lookup_kwarg_since: date.today() + timedelta(days=1), self.lookup_kwarg_until: date.today() + timedelta(days=365)}))
        self.links.insert(2, ("Demain", {self.lookup_kwarg_since: date.today() + timedelta(days=1), self.lookup_kwarg_until: date.today() + timedelta(days=2)}))
        # today and the 7 preceding days (8 days, until is exclusive)
        self.links.insert(2, ("8 jours + demain", {self.lookup_kwarg_since: date.today() - timedelta(days=7), self.lookup_kwarg_until: date.today() + timedelta(days=2)}))


@admin.action(description="Dupliquer les commandes de la date sélectionnée la plus ancienne vers les plus récentes, par livraison hebdo")
def duplicate_delivery_date_orders(modeladmin, request, queryset):
    original_delivery_dates = {}
    for delivery_date in queryset.order_by("date"):
        if delivery_date.weekly_delivery not in original_delivery_dates:
            original_delivery_dates[delivery_date.weekly_delivery] = delivery_date
        else:
            delivery_date.duplicate_orders_from(original_delivery_dates[delivery_date.weekly_delivery])


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    fields = ["customer", "total_price"]
    readonly_fields = ["customer", "total_price"]
    can_delete = True
    show_change_link = True


class ActiveCustomerDeliveryFilter(admin.RelatedFieldListFilter):
    """weekly_delivery filter, restricted to deliveries of active customers."""

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        return field.get_choices(include_blank=False, limit_choices_to={"customer__is_active": True}, ordering=ordering)


class SingleDateFilter(admin.SimpleListFilter):
    """Calendar (HTML5 date input) to filter delivery dates on one exact day."""

    title = "date précise"
    parameter_name = "exact_date"
    template = "admin/boulange/single_date_filter.html"

    def lookups(self, request, model_admin):
        return ()

    def has_output(self):
        # render the date picker even though there are no fixed choices
        return True

    def choices(self, changelist):
        other_params = {key: value for key, value in changelist.get_filters_params().items() if key != self.parameter_name}
        return [
            {
                "value": self.value() or "",
                "selected": bool(self.value()),
                "other_params": other_params,
                "clear_query_string": changelist.get_query_string(remove=[self.parameter_name]),
            }
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return queryset
        return queryset.filter(date=parsed)


class DeliveryDateAdmin(admin.ModelAdmin):
    list_display = ("weekly_delivery", "date", "active")
    list_filter = ("active", ("date", MyDateFilter), SingleDateFilter, "weekly_delivery__day_of_week", ("weekly_delivery", ActiveCustomerDeliveryFilter))
    readonly_fields = ("date", "weekly_delivery")
    inlines = [OrderInline]
    search_fields = [
        "weekly_delivery__customer__display_name",
        "weekly_delivery__customer__username",
        "date",
    ]
    actions = [duplicate_delivery_date_orders]

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if "/autocomplete/" in request.path:
            return queryset.filter(date__gte=date.today()).filter(active=True), may_have_duplicates
        return queryset, may_have_duplicates

    def has_add_permission(self, request):
        return False


admin.site.register(WeeklyDelivery, WeeklyDeliveryAdmin)
admin.site.register(DeliveryDate, DeliveryDateAdmin)


@admin.action(description="Annuler les paniers sélectionnés et réinitialiser le statut des commandes liées")
def cancel_checkouts(modeladmin, request, queryset):
    for checkout in queryset.all():
        for order in checkout.order_set.all():
            order.validated = False
            order.checkout = None
            order.save()


class CheckoutAdmin(admin.ModelAdmin):
    actions = [cancel_checkouts]
    fields = ["remote_id", "customer"]
    inlines = [OrderInline]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Checkout, CheckoutAdmin)


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 3
    autocomplete_fields = ["product"]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "quantity":
            # default new order lines to 1 (existing saved lines keep their value)
            field.initial = 1
        return field


class OrderAdmin(admin.ModelAdmin):
    list_display = ("customer", "delivery_date", "total_price")
    model = Order
    inlines = [OrderLineInline]
    save_as = True
    autocomplete_fields = ["delivery_date", "customer"]
    # A per-customer sidebar would list every customer that ever ordered (200+ entries),
    # so the customer is reached through the search box instead.
    list_filter = [("delivery_date__date", MyDateFilter), "customer__is_professional", "validated"]
    search_fields = ["customer__display_name", "customer__username", "customer__email"]
    date_hierarchy = "delivery_date__date"

    def get_queryset(self, request):
        # total_price walks the lines of every listed order: fetch them in one go rather
        # than emitting a query per row of the changelist.
        return super().get_queryset(request).select_related("customer", "delivery_date__weekly_delivery").prefetch_related("lines__product")

    @admin.display(description="Total")
    def total_price(self, obj):
        return f"{obj.total_price:.2f} €"

    class Media:
        js = ("boulange/admin_order_price.js",)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["order_product_prices"] = {p.id: float(p.price) for p in Product.objects.all()}
        extra_context["order_customers"] = {c.id: {"pro": c.is_professional, "discount": c.pro_discount_percentage} for c in Customer.objects.all()}
        extra_context["order_tva"] = TVA
        obj = self.get_object(request, object_id) if object_id else None
        extra_context["order_price_initial"] = f"{obj.total_price:.2f} €" if obj is not None else "0.00 €"
        return super().changeform_view(request, object_id, form_url, extra_context)


admin.site.register(Order, OrderAdmin)


class SettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "value")
    search_fields = ["name"]
    save_as = True


admin.site.register(Settings, SettingsAdmin)
