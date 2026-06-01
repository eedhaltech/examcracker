from django import template
from questions.models import Question

register = template.Library()


@register.filter
def question_count_for_level(level):
    return Question.objects.filter(level=level).count()


@register.filter
def tojson(value):
    import json
    return json.dumps(value)


@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key)
    return None
