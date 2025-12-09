import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models

from boulange import SPECIAL_UNITS_WEIGHTS
from boulange.templatetags.boulange_tags import bround

TVA = 5.5


class Settings(models.Model):
    name = models.CharField(max_length=200, unique=True)
    value = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name}={self.value}"

    class Meta:
        verbose_name = "Paramètre"


class Ingredient(models.Model):
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=10)
    per_unit_price = models.DecimalField(max_digits=5, decimal_places=3, help_text="price per Kg, liter or unit")
    soaking_ingredient = models.ForeignKey("Ingredient", on_delete=models.PROTECT, null=True, blank=True)
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
    # recipe quantities are set for a given number of units
    nb_units = models.IntegerField(default=1)
    # baking is set as a multiple of nb_units - can't divide
    baked_by_batch = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    display_priority = models.IntegerField(default=0)
    is_bread = models.BooleanField(default=False)
    available_mondays = models.BooleanField(default=True)
    available_tuesdays = models.BooleanField(default=True)
    available_wednesdays = models.BooleanField(default=True)
    available_thursdays = models.BooleanField(default=True)
    available_fridays = models.BooleanField(default=True)
    available_saturdays = models.BooleanField(default=True)
    available_sundays = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}/{self.ref}"

    def is_available_on_day(self, day_int):
        match day_int:
            case 0:
                return self.available_mondays
            case 1:
                return self.available_tuesdays
            case 2:
                return self.available_wednesdays
            case 3:
                return self.available_thursdays
            case 4:
                return self.available_fridays
            case 5:
                return self.available_saturdays
            case 6:
                return self.available_sundays

    def get_short_recipe_name(self):
        return f"{self.name.split(' (')[0]}/{self.ref}"

    @property
    def cost_price(self):
        price = 0
        for line in self.raw_ingredients.all():
            unit_divisor = 1
            if line.ingredient.unit == "g":
                unit_divisor = 1000
            price += Decimal(line.quantity) * line.ingredient.per_unit_price / unit_divisor
        if self.orig_product:
            for line in self.orig_product.raw_ingredients.all():
                unit_divisor = 1
                if line.ingredient.unit == "g":
                    unit_divisor = 1000
                price += Decimal(line.quantity) * Decimal(self.coef) * line.ingredient.per_unit_price / unit_divisor

        return price / Decimal(self.nb_units)

    @property
    def weight(self):
        weight = 0
        for line in self.raw_ingredients.all():
            if line.ingredient.unit == "g":
                weight += line.quantity
            elif line.ingredient.unit in SPECIAL_UNITS_WEIGHTS:
                weight += line.quantity * SPECIAL_UNITS_WEIGHTS[line.ingredient.unit]
            else:
                raise ValueError(f"Can't add weight for {line.ingredient.name}!")
        if self.orig_product:
            for line in self.orig_product.raw_ingredients.all():
                if line.ingredient.unit == "g":
                    weight += line.quantity * self.coef
                elif line.ingredient.unit in SPECIAL_UNITS_WEIGHTS:
                    weight += line.quantity * SPECIAL_UNITS_WEIGHTS[line.ingredient.unit] * self.coef
                else:
                    raise ValueError(f"Can't add weight for {line.ingredient.name}!")
        return weight / self.nb_units

    def get_processed_ingredients(self):
        ingredients = {"direct": defaultdict(int), "base_product": defaultdict(int), "preparations": defaultdict(int)}
        base_ingredients = []
        if self.orig_product:
            base_ingredients = self.orig_product.raw_ingredients.all()
        for ingref, coef, inglist in [("direct", 1, self.raw_ingredients.all()), ("base_product", self.coef, base_ingredients)]:
            for line in inglist:
                qty = line.quantity * coef / self.nb_units
                ingredients[ingref][line.ingredient] += qty
                if line.ingredient.soaking_ingredient:
                    soaking_coef = line.ingredient.soaking_coef
                    ingredients[ingref][line.ingredient] += qty * soaking_coef
                    ingredients[ingref][line.ingredient.soaking_ingredient] -= qty * soaking_coef
                    ingredients["preparations"][line.ingredient] += qty
                    ingredients["preparations"][line.ingredient.soaking_ingredient] += qty * soaking_coef
                if line.ingredient.name.startswith("Levain"):
                    ingredients["preparations"][line.ingredient] += qty
        return ingredients

    def get_batch_weight(self):
        "weight of orig product pâton, only for products that need a sub-batch"
        if not self.orig_product:
            return 0
        weight = 0
        for ing, ing_weight in self.get_processed_ingredients()["base_product"].items():
            if ing.unit in SPECIAL_UNITS_WEIGHTS:
                ing_weight *= SPECIAL_UNITS_WEIGHTS[ing.unit]
            weight += ing_weight
        return weight

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


class ResetAccountToken(models.Model):
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(default=datetime.now)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)


class WeeklyDelivery(models.Model):
    # 3 types
    # - allowed_customers set : accessible seulement aux clients listés
    # - public_delivery_point True : accessible à tous sauf les pros
    # - public_delivery_point False + attaché un un customer pro (accessible seulement par lui)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    BATCH_TARGET = {
        "SAME_DAY": "same day",
        "PREVIOUS_DAY": "previous day",
    }
    batch_target = models.CharField(max_length=20, choices=BATCH_TARGET, default="SAME_DAY")
    public_delivery_point = models.BooleanField(default=True)
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
    allowed_customers = models.ManyToManyField(Customer, related_name="private_weekly_deliveries", blank=True)

    def get_available_products(self):
        products = Product.objects.filter(active=True).order_by("name")
        return [p for p in products if p.is_available_on_day(self.day_of_week)]

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

    def get_total(self):
        total = 0
        for order in self.order_set.all():
            total += order.total_price
        return total

    def duplicate_commands_from(self, original_delivery_date):
        for order in original_delivery_date.order_set.all():
            order.duplicate_to_delivery_date(self)


class DeliveryBatch(dict):
    def add_line(self, order_line):
        dd = order_line.order.delivery_date
        if dd not in self:
            self[dd] = {}
        if order_line.product not in self[dd]:
            self[dd][order_line.product] = 0
        self[dd][order_line.product] += order_line.quantity

    def finalize(self):
        for dd in self:
            new_dict = {key: value for key, value in sorted(self[dd].items(), key=lambda items: items[0].display_priority, reverse=True)}
            self[dd].clear()
            self[dd].update(new_dict)


class BakeryBatch(dict):
    def __init__(self):
        self.temp_products = defaultdict(int)
        self.sub_batches = defaultdict(dict)
        self.nb_breads = 0

    def add_line(self, order_line):
        self.temp_products[order_line.product] += order_line.quantity

    def finalize_product(self, product, line_quantity):
        all_ingredients = product.get_processed_ingredients()
        if product.baked_by_batch and line_quantity % product.nb_units != 0:
            # adjust quantities for products that need to be batch-baked
            line_quantity += product.nb_units - (line_quantity % product.nb_units)
        if all_ingredients["direct"] and product.orig_product:
            # need sub-batch
            self.sub_batches[product.orig_product][product] = dict()
            for ing, qty in all_ingredients["direct"].items():
                self.sub_batches[product.orig_product][product][ing] = qty * product.nb_units
            self.sub_batches[product.orig_product][product]["pâton"] = product.get_batch_weight() * line_quantity
        if product.is_bread:
            self.nb_breads += line_quantity
        if product.orig_product:
            base_product = product.orig_product
            ing_ref = "base_product"
        else:
            base_product = product
            ing_ref = "direct"
        if base_product not in self:
            self[base_product] = {}
        if "ingredients" not in self[base_product]:
            self[base_product]["ingredients"] = {}
            self[base_product]["division"] = {}
        if product not in self[base_product]["division"]:
            self[base_product]["division"][product] = 0
        self[base_product]["division"][product] += line_quantity
        for ingredient, ing_qty in all_ingredients[ing_ref].items():
            quantity = line_quantity * ing_qty
            if ingredient not in self[base_product]["ingredients"]:
                self[base_product]["ingredients"][ingredient] = 0
            self[base_product]["ingredients"][ingredient] += quantity

    def finalize(self):
        for product, qty in self.temp_products.items():
            self.finalize_product(product, qty)
        for product in self:
            self[product]["weight"] = 0
            for ingredient in self[product]["ingredients"]:
                ing_weight = self[product]["ingredients"][ingredient]
                if ingredient.unit in SPECIAL_UNITS_WEIGHTS:
                    ing_weight *= SPECIAL_UNITS_WEIGHTS[ingredient.unit]
                self[product]["weight"] += ing_weight
        new_dict = {key: value for key, value in sorted(self.items(), key=lambda items: items[0].display_priority, reverse=True)}
        for base_product in new_dict:
            new_dict[base_product]["division"] = {product: qty for product, qty in new_dict[base_product]["division"].items()}
        self.clear()
        self.update(new_dict)
        self.sub_batches.default_factory = None


class PreparationBatch(dict):
    def __init__(self):
        self["levain"] = {}
        self["trempage"] = {}
        self.temp_products = defaultdict(int)

    def add_line(self, order_line):
        self.temp_products[order_line.product] += order_line.quantity

    def finalize_product(self, product, line_quantity):
        if product.baked_by_batch and line_quantity % product.nb_units != 0:
            # adjust quantities for products that need to be batch-baked
            line_quantity += product.nb_units - (line_quantity % product.nb_units)
        for ingredient, ing_qty in product.get_processed_ingredients()["preparations"].items():
            if ingredient.name.startswith("Levain"):
                if ingredient not in self["levain"]:
                    self["levain"][ingredient] = 0
                self["levain"][ingredient] += ing_qty * line_quantity
            elif ingredient.soaking_ingredient:
                if ingredient not in self["trempage"]:
                    self["trempage"][ingredient] = {"dry": 0, "soaking_qty": 0}
                quantity = ing_qty * line_quantity
                self["trempage"][ingredient]["dry"] += quantity
                self["trempage"][ingredient]["soaking_qty"] += quantity * ingredient.soaking_coef
                self["trempage"][ingredient]["soaking_ingredient"] = ingredient.soaking_ingredient
                if ingredient.name == "Flocons de riz":
                    self["trempage"][ingredient]["warning"] = "⚠ prévoir 10% de marge"

    def _refresh_levain(self, initial_qty, target_qty, water_percentage):
        missing = target_qty - initial_qty
        water = missing * water_percentage / 100
        flour = missing - water
        return flour, water

    def levain_froment_recipe(self):
        levfrom = Ingredient.objects.get(name="Levain froment")
        if levfrom not in self["levain"]:
            return {}
        qty = self["levain"][levfrom]
        try:
            nb_steps = int(Settings.objects.get(name="Nb steps levain").value)
        except Settings.DoesNotExist:
            nb_steps = 2
        if nb_steps == 3:
            flour1, water1 = self._refresh_levain(100, 1000, 65)
            flour2, water2 = self._refresh_levain(1000, 3000, 50)
            flour3, water3 = self._refresh_levain(3000, qty, 40)
            return [
                {
                    "title": "1er rafraîchi (cible 1000 g)",
                    "lines": [
                        "100 g de levain chef",
                        f"{bround(water1, 'eau')} g d'eau chaude (60%)",
                        f"{bround(flour1, 'farine')} g de farine de froment (40%)",
                    ],
                },
                {
                    "title": "2nd rafraîchi (cible 3000 g)",
                    "lines": [
                        "1000 g de levain",
                        f"{bround(water2, 'eau')} g d'eau tiède (50%)",
                        f"{bround(flour2, 'farine')} g de farine de froment (50%)",
                    ],
                },
                {
                    "title": f"3ème rafraîchi (cible {bround(qty, 'total')} g)",
                    "lines": [
                        "3000 g de levain",
                        f"{bround(water3, 'eau')} g d'eau tiède (40%)",
                        f"{bround(flour3, 'farine')} g de farine de froment (60%)",
                    ],
                },
            ]
        else:
            flour1, water1 = self._refresh_levain(100, 300, 60)
            flour2, water2 = self._refresh_levain(300, qty, 50)
            return [
                {
                    "title": "1er rafraîchi (cible 300 g)",
                    "lines": [
                        "100 g de levain chef",
                        f"{bround(water1, 'eau')} g d'eau chaude (60%)",
                        f"{bround(flour1, 'farine')} g de farine de froment (40%)",
                    ],
                },
                {
                    "title": f"2nd rafraîchi (cible {bround(qty, 'total')} g)",
                    "lines": [
                        "300 g de levain",
                        f"{bround(water2, 'eau')} g d'eau tiède (50%)",
                        f"{bround(flour2, 'farine')} g de farine de froment (50%)",
                    ],
                },
            ]

    def levain_petit_epeautre_recipe(self):
        levep = Ingredient.objects.get(name="Levain de petit epeautre")
        if levep not in self["levain"]:
            return {}
        qty = self["levain"][levep]
        return [
            {
                "title": f"1er rafraîchi (cible {bround(qty, 'total')} g)",
                "lines": [
                    f"{qty*7/110:.0f} g de levain de froment",
                    f"{qty*58/110:.0f} g de farine de petit épeautre",
                    f"{qty*44/110:.0f} g d'eau",
                    f"{qty*1/110:.0f} g de sel",
                ],
            }
        ]

    def levain_sarrasin_recipe(self):
        levsar = Ingredient.objects.get(name="Levain sarrasin")
        if levsar not in self["levain"]:
            return {}
        qty = self["levain"][levsar]
        try:
            nb_steps = int(Settings.objects.get(name="Nb steps levain").value)
        except Settings.DoesNotExist:
            nb_steps = 2
        if nb_steps == 3:
            # including future levain chef
            qty += 20
            flour1, water1 = self._refresh_levain(20, 100, 50)
            flour2, water2 = self._refresh_levain(100, 300, 50)
            flour3, water3 = self._refresh_levain(300, qty, 43)
            return [
                {
                    "title": "1er rafraîchi (cible 100 g)",
                    "lines": [
                        "20 g de levain chef",
                        f"{bround(water1, 'eau')} g d'eau chaude (50%)",
                        f"{bround(flour1, 'farine')} g de farine de sarrasin (50%)",
                    ],
                },
                {
                    "title": "2nd rafraîchi (cible 300 g)",
                    "lines": [
                        "100 g de levain chef",
                        f"{bround(water2, 'eau')} g d'eau chaude (50%)",
                        f"{bround(flour2, 'farine')} g de farine de sarrasin (50%)",
                    ],
                },
                {
                    "title": f"3ème rafraîchi (cible {bround(qty, 'total')} g)",
                    "lines": [
                        "300 g de levain",
                        f"{bround(water3, 'eau')} g d'eau tiède (43%)",
                        f"{bround(flour3, 'farine')} g de farine de sarrasin (67%)",
                    ],
                },
            ]
        else:
            # including future levain chef
            qty += 20
            flour1, water1 = self._refresh_levain(20, 100, 50)
            flour2, water2 = self._refresh_levain(100, qty, 50)
            return [
                {
                    "title": "1er rafraîchi (cible 100 g)",
                    "lines": [
                        "20 g de levain chef",
                        f"{bround(water1, 'eau')} g d'eau chaude (50%)",
                        f"{bround(flour1, 'farine')} g de farine de sarrasin (50%)",
                    ],
                },
                {
                    "title": f"2nd rafraîchi (cible {bround(qty, 'total')} g)",
                    "lines": [
                        "100 g de levain",
                        f"{bround(water2, 'eau')} g d'eau tiède (50%)",
                        f"{bround(flour2, 'farine')} g de farine de sarrasin (50%)",
                    ],
                },
            ]

    def finalize(self):
        for product, qty in self.temp_products.items():
            self.finalize_product(product, qty)


class Actions(dict):
    def __init__(self):
        self["delivery"] = DeliveryBatch()
        self["bakery"] = BakeryBatch()
        self["preparation"] = PreparationBatch()

    def add_order_for_delivery(self, order):
        for line in order.lines.all():
            self["delivery"].add_line(line)

    def add_order_for_bakery(self, order):
        for line in order.lines.all():
            self["bakery"].add_line(line)

    def add_order_for_preparation(self, order):
        for line in order.lines.all():
            self["preparation"].add_line(line)

    def finalize(self):
        "To be called after all orders have been processed"
        for batch in self.values():
            batch.finalize()

class Checkout(models.Model):
    remote_id = models.CharField(max_length=64)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    delivery_date = models.ForeignKey(DeliveryDate, on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)
    validated = models.BooleanField(default=True)
    checkout = models.ForeignKey(Checkout, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return f"{self.customer}/{self.delivery_date}"

    @property
    def total_price(self):
        total = 0
        for line in self.lines.all():
            total += line.get_price()
        return total

    def get_actions(self, target_day, actions=None):
        if not actions:
            actions = Actions()
        if self.delivery_date.date == target_day:
            actions.add_order_for_delivery(self)
        if self.delivery_date.weekly_delivery.batch_target == "SAME_DAY":
            bakery_day = self.delivery_date.date
        elif self.delivery_date.weekly_delivery.batch_target == "PREVIOUS_DAY":
            bakery_day = self.delivery_date.date - timedelta(days=1)
        if target_day == bakery_day:
            actions.add_order_for_bakery(self)
        preparation_day = bakery_day - timedelta(days=1)
        if target_day == preparation_day:
            actions.add_order_for_preparation(self)
        return actions

    def duplicate_to_delivery_date(self, delivery_date):
        new_order = Order(customer=self.customer, delivery_date=delivery_date, notes=self.notes)
        new_order.save()
        for line in self.lines.all():
            new_line = OrderLine(order=new_order, product=line.product, quantity=line.quantity)
            new_line.save()
        return new_order

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
        return total

    class Meta:
        ordering = ["product__name"]

