from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import ProfilEmploye


@receiver(post_save, sender=User)
def creer_profil_employe(sender, instance, created, **kwargs):
    """Crée automatiquement un ProfilEmploye quand un User est créé."""
    if created:
        ProfilEmploye.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def sauvegarder_profil(sender, instance, **kwargs):
    if hasattr(instance, 'profil'):
        instance.profil.save()