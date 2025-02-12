from django import forms

from boulange import models


class OrderForm(forms.ModelForm):
    class Meta:
        model = models.Order
        fields = ["customer", "delivery_date"]


class OrderLineForm(forms.ModelForm):
    class Meta:
        model = models.OrderLine
        fields = ["product", "quantity"]
