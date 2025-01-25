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


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = "__all__"


class ProductLineSerializer(serializers.ModelSerializer):
    ingredient = serializers.StringRelatedField()

    class Meta:
        model = ProductLine
        fields = ["ingredient", "quantity"]


class ProductSerializer(serializers.ModelSerializer):
    raw_ingredients = ProductLineSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "ref",
            "price",
            "raw_ingredients",
            "cost_price",
            "weight",
            "active",
            "orig_product",
            "coef",
            "nb_units",
        ]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "email",
            "username",
            "display_name",
            "is_professional",
            "pro_discount_percentage",
            "address",
        ]


class WeeklyDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyDelivery
        fields = "__all__"


class DeliveryDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryDate
        fields = "__all__"


class OrderLineSerializer(serializers.ModelSerializer):
    product = serializers.SlugRelatedField(slug_field="ref", read_only=True)

    class Meta:
        model = OrderLine
        fields = ["product", "quantity"]


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = ["id", "customer", "delivery_date", "total_price", "lines"]

    def run_validation(self, data):
        self.lines_data = []

        for line in data["lines"]:
            self.lines_data.append(
                {
                    "product": Product.objects.get(ref=line["product"]),
                    "quantity": line["quantity"],
                }
            )
        validated_data = super().run_validation(data=data)
        validated_data.pop("lines")
        return validated_data

    def create(self, validated_data):
        order = Order.objects.create(**validated_data)
        for line in self.lines_data:
            OrderLine.objects.create(order=order, **line)
        return order
