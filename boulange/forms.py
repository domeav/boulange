from django import forms
import datetime


class DateForm(forms.Form):
    date = forms.DateField(initial=datetime.date.today)
    template_name = "boulange/date_form.html"
