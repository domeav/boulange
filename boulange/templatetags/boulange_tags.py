from django.template.defaultfilters import register

SALT = "Sel"
EGGS = "Oeufs"

@register.filter(name="dict_key")
def dict_key(d, k):
    """Returns the given key from a dictionary."""
    return d.get(k, None)


@register.filter(name="bround")
def bround(value, ing=None):
    """Rounds depending on ingredient"""
    if hasattr(ing, "name"):
        ing = ing.name
    if ing == SALT:
        return round(value)
    elif ing is None or ing == EGGS:
        return value
    else:
        return round(value / 10) * 10
