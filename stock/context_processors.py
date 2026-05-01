from .models import DemandeArrivage, Boutique


def demandes_en_attente(request):
    if not request.user.is_authenticated:
        return {}
    try:
        if request.user.profil.est_proprietaire:
            boutiques = Boutique.objects.filter(proprietaire=request.user)
            nb = DemandeArrivage.objects.filter(
                boutique__in=boutiques,
                statut='en_attente'
            ).count()
            return {'nb_demandes_attente': nb}
    except Exception:
        pass
    return {'nb_demandes_attente': 0}