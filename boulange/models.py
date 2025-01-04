from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.db.models import Q

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

    def to_dict(self):
        obj = {'name': self.name,
               'ref': self.ref,
               'price': round(float(self.price), 2),
               'active': self.active,
               'nb_units': self.nb_units,
               'cost_price': round(float(self.cost_price()), 2)}
        if self.orig_product:
            obj['orig_product'] = self.orig_product.ref
            obj['coef'] = self.coef
        else:
            obj['ingredients'] = [i.to_dict() for i in self.productline_set.all()]
        return obj
            
    
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

    def to_dict(self):
        return {'ingredient': self.ingredient.name,
                'quantity': round(self.quantity, 2)}
    
    def __str__(self):
        return self.display_dry()


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    is_professional = models.BooleanField(default=False)
    pro_discount_percentage = models.FloatField(default=5.0)
    address = models.CharField(max_length=400, blank=True, null=True)

    def to_dict(self):
        return {'user': self.__str__(),
                'is_professional': self.is_professional,
                'pro_discount_percentage': self.pro_discount_percentage}
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}({self.user.email})"


class WeeklyDelivery(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    BATCH_TARGET = {
        "SAME_DAY": "same day",
        "PREVIOUS_DAY": "previous day",
    }
    batch_target = models.CharField(
        max_length=20, choices=BATCH_TARGET, default="SAME_DAY"
    )
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
        return f"{self.customer.user}: {self.DAY_OF_WEEK[self.day_of_week]}"

    class Meta:
        ordering = ["day_of_week", "customer"]


class DeliveryDate(models.Model):
    weekly_delivery = models.ForeignKey(WeeklyDelivery, on_delete=models.CASCADE, null=True)
    date = models.DateField()
    active = models.BooleanField(default=True)

    def __str__(self):
        inactive = ""
        if not self.active:
            inactive = "[OFF] "
        return f"{inactive}{self.weekly_delivery}: {self.date}"

    def to_dict(self):
        return {'date': self.date.isoformat(),
                'active': self.active,
                'user': str(self.weekly_delivery.customer.user),
                'address': self.weekly_delivery.customer.address,
                "orders": [o.to_dict() for o in self.order_set.all()]}
    
    class Meta:
        ordering = ["date", "weekly_delivery"]


def fetch_orders_for_action(year, month, day):
    target_day = date(year, month, day)
    weekdays_list = list(range(7)) + list(range(7))
    weekdays = weekdays_list[target_day.weekday:target_day.weekday+3]
    orders = {'delivery': [],
              'bakery': [],
              'preparation': []}
    three_days_orders = Orders.objects.filter(
         Q(delivery_date__date__gte=target_day),
         Q(delivery_date__date__lte=target_day+timedelta(days+2)))
    
    for order in three_days_orders:
        if order.weekly_delivery.day_of_week == target_day.weekday or order.delivery_date.date == target_day:
            orders['delivery'].append(order)
            if order.weekly_delivery.batch_target == 'SAME_DAY':
                orders['bakery'].append(order)
        elif order.weekly_delivery.day_of_week == weekdays[target_day.weekday+1] or order.delivery_date.date == target_day + timedelta(1):
            if order.weekly_delivery.batch_target == 'SAME_DAY':
                orders['preparation'].append(order)
            elif order.weekly_delivery.batch_target == 'PREVIOUS_DAY':
                orders['bakery'].append(order)
        elif order.weekly_delivery.day_of_week == weekdays[target_day.weekday+2] or order.delivery_date.date == target_day + timedelta(2):
            if order.weekly_delivery.batch_target == 'PREVIOUS_DAY':
                orders['preparation'].append(order)
    return orders

        
class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    delivery_date = models.ForeignKey(
        DeliveryDate, on_delete=models.CASCADE, blank=True, null=True
    )

    def to_dict(self):
        return {'customer': self.customer.to_dict(),
                'lines': [l.to_dict() for l in self.orderline_set.all()],
                'price': round(float(self.get_total_price())),
                'date': self.delivery_date.date.isoformat(),
                'where': str(self.delivery_date.weekly_delivery)}
        
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

    def to_dict(self):
        return {'product': self.product.ref,
                'quantity': self.quantity}
    
    def get_price(self):
        total = self.product.price * self.quantity
        if self.order.customer.is_professional:
            total = (total - total * Decimal(TVA / 100)) * Decimal(
                1 - self.order.customer.pro_discount_percentage / 100
            )
        return round(total, 2)
