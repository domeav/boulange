from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models

TVA = 5.5


class Ingredient(models.Model):
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=10)
    per_unit_price = models.DecimalField(max_digits=5, decimal_places=3, help_text="price per Kg, liter or unit")
    needs_soaking = models.BooleanField(default=False)
    # qty of water needed is ing weight * coef
    soaking_coef = models.FloatField(default=1)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [models.Index(fields=["name"])]
        ordering = ["name"]


class Product(models.Model):
    name = models.CharField(max_length=200)
    ref = models.CharField(max_length=20, unique=True)
    price = models.DecimalField(max_digits=5, decimal_places=2)
    active = models.BooleanField(default=True)
    # if orig_product is set we'll be using its ingredients with quantity * coef
    orig_product = models.ForeignKey("Product", on_delete=models.CASCADE, null=True, blank=True)
    # when product_lines are defined in another product (orig_product)
    coef = models.FloatField(default=1)
    nb_units = models.IntegerField(default=1)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name}/{self.ref}"

    def base_recipe_name(self):
        return f"{self.name.split(' (')[0]}/{self.ref}"

    @property
    def cost_price(self):
        price = 0
        product = self.orig_product or self
        for line in product.raw_ingredients.all():
            unit_divisor = 1
            if line.ingredient.unit in ("g", "ml"):
                unit_divisor = 1000
            price += Decimal(line.quantity) * line.ingredient.per_unit_price / unit_divisor

        return round(price * Decimal(self.coef) / Decimal(self.nb_units), 2)

    @property
    def weight(self):
        weight = 0
        product = self.orig_product or self
        for line in product.raw_ingredients.all():
            if line.ingredient.unit in ("g", "ml"):
                weight += line.quantity
            elif line.ingredient.name == "Oeufs":
                weight += line.quantity * 60
            else:
                raise ValueError(f"Can't add weight for {line.ingredient.name}!")
        return round(weight * self.coef / self.nb_units / 10) * 10

    def get_base_product_and_coef(self):
        product = self
        coef = 1
        if self.orig_product:
            product = self.orig_product
            coef = self.coef
        return product, coef

    def get_ingredients(self):
        "Eventually fetch ingredient list from base product"
        product, coef = self.get_base_product_and_coef()
        for line in product.raw_ingredients.all():
            yield (line.ingredient, line.quantity * coef)

    def get_ref_queryset(self):
        import pdb

        pdb.set_trace()
        ref = self.request.query_params.get("ref")
        return Product.objects.get(ref=ref)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["ref"]),
        ]
        verbose_name = "Produit"
        ordering = ["name"]


class ProductLine(models.Model):
    product = models.ForeignKey(Product, related_name="raw_ingredients", on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField()

    class Meta:
        ordering = ["ingredient__name"]


class Customer(AbstractUser):
    display_name = models.CharField(max_length=200, unique=True)
    is_professional = models.BooleanField(default=False)
    pro_discount_percentage = models.FloatField(default=5.0, blank=True)
    address = models.CharField(max_length=400, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.display_name}"

    class Meta:
        verbose_name = "Client"
        ordering = ["display_name"]


class WeeklyDelivery(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    BATCH_TARGET = {
        "SAME_DAY": "same day",
        "PREVIOUS_DAY": "previous day",
    }
    batch_target = models.CharField(max_length=20, choices=BATCH_TARGET, default="SAME_DAY")
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
    notes = models.TextField(blank=True, null=True)

    def generate_delivery_dates(self):
        if not self.active:
            return
        current = date.today()
        one_year = current + timedelta(days=365)
        existing_dates = set()
        for ddate in DeliveryDate.objects.all():
            existing_dates.add((ddate.weekly_delivery.id, ddate.date))
        while current <= one_year:
            if current.weekday() == self.day_of_week:
                if (self.id, current) not in existing_dates:
                    delivery_date = DeliveryDate(weekly_delivery=self, date=current)
                    delivery_date.save()
            current += timedelta(days=1)

    def __str__(self):
        return f"{self.customer}: {self.DAY_OF_WEEK[self.day_of_week]}"

    def save(self, **kwargs):
        super().save(**kwargs)
        self.generate_delivery_dates()

    class Meta:
        ordering = ["day_of_week", "customer"]
        unique_together = ("customer", "day_of_week")
        verbose_name = "Livraison hebdo"
        verbose_name_plural = "Livraisons hebdo"


class DeliveryDate(models.Model):
    weekly_delivery = models.ForeignKey(WeeklyDelivery, on_delete=models.CASCADE, null=True)
    date = models.DateField()
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        inactive = ""
        if not self.active:
            inactive = "[OFF] "
        return f"{inactive}{self.weekly_delivery}: {self.date}"

    class Meta:
        ordering = ["date", "weekly_delivery"]
        verbose_name = "Date de livraison"
        verbose_name_plural = "Dates de livraison"


class DivisionBatch(dict):
    def add_line(self, order_line):
        key = str(order_line.product)
        if key not in self:
            self[key] = 0
        self[key] += order_line.quantity

    def round(self):
        pass


class DeliveryBatch(dict):
    def add_line(self, order_line):
        dd = order_line.order.delivery_date
        if dd not in self:
            self[dd] = {}
        key = str(order_line.product)
        if key not in self[dd]:
            self[dd][key] = 0
        self[dd][key] += order_line.quantity

    def round(self):
        pass


class BakeryBatch(dict):
    water_key = "Eau"

    def add_line(self, order_line):
        base_product, _ = order_line.product.get_base_product_and_coef()
        product_key = base_product.base_recipe_name()
        if product_key not in self:
            self[product_key] = {self.water_key: 0}
        for ingredient, ing_qty in order_line.product.get_ingredients():
            ingredient_key = str(ingredient)
            if ingredient.name == "Eau":
                ingredient_key = self.water_key
            elif ingredient.needs_soaking:
                ingredient_key += " (trempé)"
            base_qty = order_line.quantity * ing_qty
            quantity = base_qty / base_product.nb_units
            if ingredient.needs_soaking:
                quantity += base_qty / base_product.nb_units * ingredient.soaking_coef
                self[product_key][self.water_key] -= base_qty / base_product.nb_units * ingredient.soaking_coef
            if ingredient_key not in self[product_key]:
                self[product_key][ingredient_key] = 0
            self[product_key][ingredient_key] += quantity

    def round(self):
        for product in self:
            for ingredient in self[product]:
                if ingredient == "Sel":
                    self[product][ingredient] = round(self[product][ingredient])
                else:
                    self[product][ingredient] = round(self[product][ingredient] / 10) * 10

    def sorted(self):
        new_dict = {}
        order = ['Sarrasin 100%/GSa', 'Seigle 70%/GSe', "Semi-complet lin/GL", "Semi-complet kasha/GK", "Semi-complet nature/GN", "Brioche raisin/BR", "Brioche chocolat/BC"]
        for product_key in order:
            if product_key in self:
                new_dict[product_key] = self[product_key]
        for product_key in self.keys() - set(order):
            new_dict[product_key] = self[product_key]
        return new_dict


class PreparationBatch(dict):
    def __init__(self):
        super().__init__()
        self["levain"] = {}
        self["trempage"] = {}

    def add_line(self, order_line):
        for ingredient, ing_qty in order_line.product.get_ingredients():
            if ingredient.name.startswith("Levain"):
                if ingredient.name not in self["levain"]:
                    self["levain"][ingredient.name] = 0
                self["levain"][ingredient.name] += ing_qty / order_line.product.nb_units * order_line.quantity
            elif ingredient.needs_soaking:
                if ingredient.name not in self["trempage"]:
                    self["trempage"][ingredient.name] = {"dry": 0, "water": 0}
                quantity = ing_qty / order_line.product.nb_units * order_line.quantity
                self["trempage"][ingredient.name]["dry"] += quantity
                self["trempage"][ingredient.name]["water"] += quantity * ingredient.soaking_coef
                if ingredient.name == "Flocons de riz":
                    self["trempage"][ingredient.name]["warning"] = "⚠ prévoir 10% de marge"

    def _refresh_levain(self, initial_qty, target_qty, water_percentage):
        missing = target_qty - initial_qty
        water = round(missing * water_percentage / 100)
        flour = round(missing - water)
        return flour, water

    def levain_froment_recipe(self):
        if "Levain froment" not in self["levain"]:
            return {}
        qty = self["levain"]["Levain froment"]
        flour1, water1 = self._refresh_levain(100, 300, 60)
        flour2, water2 = self._refresh_levain(300, qty, 50)
        return [
            {
                "title": "1er rafraîchi (cible 300 g)",
                "lines": [
                    "100g de levain chef",
                    f"{water1} ml d'eau chaude (60%)",
                    f"{flour1} g de farine de froment (40%)",
                ],
            },
            {
                "title": f"2nd rafraîchi (cible {qty} g)",
                "lines": [
                    "300g de levain",
                    f"{water2} ml d'eau tiède (50%)",
                    f"{flour2} g de farine de froment (50%)",
                ],
            },
        ]

    def levain_sarrasin_recipe(self):
        if "Levain sarrasin" not in self["levain"]:
            return {}
        qty = self["levain"]["Levain sarrasin"]
        # including future levain chef
        qty += 20
        flour1, water1 = self._refresh_levain(20, 100, 50)
        flour2, water2 = self._refresh_levain(100, qty, 50)
        return [
            {
                "title": "1er rafraîchi (cible 100 g)",
                "lines": [
                    "20g de levain chef",
                    f"{water1} ml d'eau chaude (50%)",
                    f"{flour1} g de farine de sarrasin (50%)",
                ],
            },
            {
                "title": f"2nd rafraîchi (cible {qty} g)",
                "lines": [
                    "100g de levain",
                    f"{water2} ml d'eau tiède (50%)",
                    f"{flour2} g de farine de sarrasin (50%)",
                ],
            },
        ]

    def round(self):
        for ingredient in self["trempage"]:
            self["trempage"][ingredient]["dry"] = round(self["trempage"][ingredient]["dry"] / 10) * 10
            self["trempage"][ingredient]["water"] = round(self["trempage"][ingredient]["water"] / 10) * 10
        for levain in self["levain"]:
            self["levain"][levain] = round(self["levain"][levain] / 10) * 10


class Actions(dict):
    def __init__(self):
        self["delivery"] = DeliveryBatch()
        self["division"] = DivisionBatch()
        self["bakery"] = BakeryBatch()
        self["preparation"] = PreparationBatch()

    def add_order_for_delivery(self, order):
        for line in order.lines.all():
            self["delivery"].add_line(line)

    def add_order_for_division(self, order):
        for line in order.lines.all():
            self["division"].add_line(line)

    def add_order_for_bakery(self, order):
        for line in order.lines.all():
            self["bakery"].add_line(line)

    def add_order_for_preparation(self, order):
        for line in order.lines.all():
            self["preparation"].add_line(line)

    def round(self):
        for batch in self.values():
            batch.round()


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    delivery_date = models.ForeignKey(DeliveryDate, on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.customer}/{self.delivery_date}"

    @property
    def total_price(self):
        total = 0
        for line in self.lines.all():
            total += line.get_price()
        return round(total, 2)

    def get_actions(self, target_day, actions=None):
        if not actions:
            actions = Actions()
        if self.delivery_date.date == target_day:
            actions.add_order_for_delivery(self)
            actions.add_order_for_division(self)
        if self.delivery_date.weekly_delivery.batch_target == "SAME_DAY":
            bakery_day = self.delivery_date.date
        elif self.delivery_date.weekly_delivery.batch_target == "PREVIOUS_DAY":
            bakery_day = self.delivery_date.date - timedelta(days=1)
        if target_day == bakery_day:
            actions.add_order_for_bakery(self)
        preparation_day = bakery_day - timedelta(days=1)
        if target_day == preparation_day:
            actions.add_order_for_preparation(self)
        actions.round()
        return actions

    class Meta:
        verbose_name = "Commande"
        ordering = ["-delivery_date", "customer"]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.quantity} {self.product.ref}"

    def get_price(self):
        total = self.product.price * self.quantity
        if self.order.customer.is_professional:
            total = (total - total * Decimal(TVA / 100)) * Decimal(1 - self.order.customer.pro_discount_percentage / 100)
        return round(total, 2)

    class Meta:
        ordering = ["product__name"]
