import nested_admin
from django.contrib import admin

from .models import (
    Customer,
    DeliveryDate,
    DeliveryPoint,
    Ingredient,
    Order,
    OrderLine,
    Recipe,
    RecipeLine,
)


class RecipeLineInline(admin.TabularInline):
    model = RecipeLine
    extra = 1


class RecipeAdmin(admin.ModelAdmin):
    inlines = [RecipeLineInline]


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


class DeliveryDateAdmin(nested_admin.NestedModelAdmin):
    inlines = [OrderInline]


admin.site.register(Ingredient)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(DeliveryPoint, DeliveryPointAdmin)
admin.site.register(Customer)
admin.site.register(DeliveryDate, DeliveryDateAdmin)
