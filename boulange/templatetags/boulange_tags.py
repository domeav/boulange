from django.template.defaultfilters import register
from django.utils.safestring import SafeString

from boulange import SPECIAL_UNITS_WEIGHTS

@register.filter(name="dict_key")
def dict_key(d, k):
    """Returns the given key from a dictionary."""
    return d.get(k, None)


@register.filter(name="bround")
def bround(value, ing=None):
    """Rounds depending on ingredient"""
    if type(ing) not in (str, SafeString):
        if ing and not ing.decimal_round:
            return round(value)
        elif ing is None or ing.name in SPECIAL_UNITS_WEIGHTS:
            return value
    return round(value / 10) * 10
