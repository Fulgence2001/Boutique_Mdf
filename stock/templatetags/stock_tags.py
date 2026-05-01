# stock/templatetags/stock_tags.py
from django import template

register = template.Library()

@register.filter
def est_proprietaire(user):
    try:
        return user.profil.est_proprietaire
    except Exception:
        return False