from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get a value from a dict by key in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def subtract(value, arg):
    return int(value) - int(arg)
