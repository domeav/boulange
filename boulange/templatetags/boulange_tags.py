from django.template.defaultfilters import register


@register.filter(name="dict_key")
def dict_key(d, k):
    """Returns the given key from a dictionary."""
    return d.get(k, None)


@register.filter(name="bround")
def bround(value, ing=None):
    """Rounds depending on ingredient"""
    if ing == "Sel":
        return round(value)
    elif ing is None or ing == "Oeufs":
        return value
    else:
        return round(value / 10) * 10
