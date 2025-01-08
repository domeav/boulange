from rest_framework import serializers

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


class IngredientSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Ingredient
        fields = "__all__"


class ProductLineSerializer(serializers.HyperlinkedModelSerializer):
    ingredient = serializers.StringRelatedField()

    class Meta:
        model = ProductLine
        fields = ["ingredient", "quantity"]


class ProductSerializer(serializers.HyperlinkedModelSerializer):
    raw_ingredients = ProductLineSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "url",
            "name",
            "ref",
            "price",
            "raw_ingredients",
            "cost_price",
            "active",
            "orig_product",
            "coef",
            "nb_units",
        ]


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "url",
            "email",
            "username",
            "is_professional",
            "pro_discount_percentage",
            "address",
        ]


class WeeklyDeliverySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = WeeklyDelivery
        fields = "__all__"


class DeliveryDateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DeliveryDate
        fields = "__all__"


class OrderLineSerializer(serializers.HyperlinkedModelSerializer):
    product = serializers.StringRelatedField()

    class Meta:
        model = OrderLine
        fields = ["product", "quantity"]


class OrderSerializer(serializers.HyperlinkedModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    delivery_date = serializers.StringRelatedField()

    class Meta:
        model = Order
        fields = ["customer", "delivery_date", "total_price", "lines"]
