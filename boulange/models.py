from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User

TVA = 5.5


class Ingredient(models.Model):
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=10)
    per_unit_price = models.DecimalField(
        max_digits=5, decimal_places=3, help_text="price per Kg, liter or unit"
    )
    needs_soaking = models.BooleanField(default=False)
    # qty of water needed is ing weight * coef
    soaking_coef = models.FloatField(default=1)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [models.Index(fields=["name"])]


class Product(models.Model):
    name = models.CharField(max_length=200)
    ref = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=5, decimal_places=2)
    active = models.BooleanField(default=True)
    # if orig_product is set we'll be using its ingredients with quantity * coef
    orig_product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, null=True, blank=True
    )
    # when product_lines are defined in another product (orig_product)
    coef = models.FloatField(default=1)
    nb_units = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.name}/{self.ref}"

    def cost_price(self):
        price = 0
        product = self.orig_product or self
        for line in product.productline_set.all():
            unit_divisor = 1
            if line.ingredient.unit in ("g", "ml"):
                unit_divisor = 1000
            price += (
                Decimal(line.quantity) * line.ingredient.per_unit_price / unit_divisor
            )

        return price * Decimal(self.coef) / Decimal(self.nb_units)

    def get_soaking_water(self):
        "Qty of water that should be used to soak ingredients"
        water = 0
        for line in self.productline_set.all():
            if line.ingredient.needs_soaking:
                water += line.quantity
        return water

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["ref"]),
        ]


class ProductLine(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField()

    def display(self, coef=1):
        "Removes water that has been used to soak ingredients"
        base_quantity = self.quantity
        hint = ""
        if self.ingredient.name == "Eau":
            if self.product.get_soaking_water():
                base_quantity -= self.product.get_soaking_water()
                hint = " (- trempage)"
        elif self.ingredient.needs_soaking:
            # add water to qty
            base_quantity *= 2
            hint = " (trempé)"
        quantity = base_quantity / self.product.nb_units * coef

        return f"{self.ingredient.name}{ hint } : {round(quantity, 2)} {self.ingredient.unit}"

    def display_dry(self, coef=1):
        quantity = self.quantity / self.product.nb_units * coef
        return f"{self.ingredient.name} : {round(quantity, 2)} {self.ingredient.unit}"

    def __str__(self):
        return self.display_dry()


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    is_professional = models.BooleanField(default=False)
    pro_discount_percentage = models.FloatField(default=5.0)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}({self.user.email})"


class DeliveryDay(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    BATCH_TARGET = {
        "SAME_DAY": "same day",
        "PREVIOUS_DAY": "previous day",
    }
    batch_target = models.CharField(
        max_length=20, choices=BATCH_TARGET, default="SAME_DAY"
    )
    address = models.CharField(max_length=400, blank=True, null=True)
    can_order_here_from_website = models.BooleanField(default=True)
    DAY_OF_WEEK = {
        0: "lundi",
        1: "mardi",
        2: "mercredi",
        3: "jeudi",
        4: "vendredi",
        5: "samedi",
        6: "dimanche",
    }
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK)

    def __str__(self):
        return f"{self.user}: {self.DAY_OF_WEEK[self.day_of_week]}"


class DeliveryDate(models.Model):
    delivery_day = models.ForeignKey(DeliveryDay, on_delete=models.CASCADE, null=True)
    date = models.DateField()

    def __str__(self):
        return f"{self.delivery_day}: {self.date}"


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    delivery_date = models.ForeignKey(DeliveryDate, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.customer.user}/{self.delivery_date}"

    def get_total_price(self):
        total = 0
        for line in self.orderline_set.all():
            total += line.get_price()
        return round(total, 2)


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.quantity} {self.product.ref}"

    def get_price(self):
        total = self.product.price * self.quantity
        if self.order.customer.is_professional:
            total = (total - total * Decimal(TVA / 100)) * Decimal(
                1 - self.order.customer.pro_discount_percentage / 100
            )
        return round(total, 2)
