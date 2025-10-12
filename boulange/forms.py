from datetime import date, timedelta

from django.forms import ModelForm, Textarea, inlineformset_factory

from .models import DeliveryDate, Order, OrderLine


class OrderForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(OrderForm, self).__init__(*args, **kwargs)
        self.fields["delivery_date"].queryset = DeliveryDate.objects.filter(date__gte=date.today()).filter(date__lte=date.today() + timedelta(days=90)).filter(active=True)

    class Meta:
        model = Order
        widgets = {
            "notes": Textarea(attrs={"rows": 1, "cols": 30}),
        }
        fields = ["delivery_date", "notes"]


OrderLineFormSet = inlineformset_factory(Order, OrderLine, fields=["product", "quantity"], can_delete=False, can_delete_extra=False)
