from django.db import models

class Ingredient(models.Model):
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=10)

class Recipe(models.Model):
    name = models.CharField(max_length=200)
    ref = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=5, decimal_places=2)
    active = models.BooleanField(default=True)

class RecipeLine(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField()
    
class DeliveryPoint(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=400)
    active = models.BooleanField(default=True)

class DeliveryDate(models.Model):
    delivery_point = models.ForeignKey(DeliveryPoint, on_delete=models.CASCADE)
    date = models.DateField()

class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    default_delivery_point = models.ForeignKey(DeliveryPoint, on_delete=models.SET_NULL, null=True)

class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    delivery_point = models.ForeignKey(DeliveryPoint, on_delete=models.PROTECT)
    delivery_date = models.ForeignKey(DeliveryDate, on_delete=models.PROTECT)

class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT)
    quantity = models.IntegerField()
