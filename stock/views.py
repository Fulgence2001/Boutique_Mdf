from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ConnexionForm, InscriptionForm
from .models import Boutique, ProfilEmploye
from functools import wraps
from django.core.exceptions import PermissionDenied

def proprietaire_requis(view_func):
    """Bloque l'accès aux employés — réservé aux propriétaires."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            profil = request.user.profil
        except Exception:
            raise PermissionDenied
        if not profil.est_proprietaire:
            messages.error(request, "Accès réservé au propriétaire.")
            return redirect('pos')  # L'employé atterrit sur la caisse
        return view_func(request, *args, **kwargs)
    return wrapper


def employe_sa_boutique(view_func):
    """S'assure que l'employé ne peut accéder qu'à sa boutique assignée."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            profil = request.user.profil
        except Exception:
            return redirect('connexion')
        # Si employé sans boutique → bloqué
        if not profil.est_proprietaire and not profil.boutique:
            messages.error(request, "Aucune boutique ne vous est assignée. Contactez votre responsable.")
            return redirect('connexion')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Connexion ──────────────────────────────────────────
def vue_connexion(request):
    if request.user.is_authenticated:
        return redirect('choisir_boutique')

    form = ConnexionForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f"Bienvenue {user.first_name or user.username} !")
        return redirect('choisir_boutique')

    # Récupère l'IP locale
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_locale = s.getsockname()[0]
        s.close()
    except Exception:
        ip_locale = "192.168.43.1"

    return render(request, 'stock/login.html', {
        'form': form,
        'ip_locale': ip_locale,
    })


# ── Inscription ────────────────────────────────────────
def vue_inscription(request):
    form = InscriptionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # Le signal crée le ProfilEmploye automatiquement
        # On le marque propriétaire car c'est lui qui s'inscrit
        user.profil.role = 'proprietaire'
        user.profil.save()
        login(request, user)
        messages.success(request, "Compte créé ! Créez votre première boutique.")
        return redirect('creer_boutique')

    return render(request, 'stock/inscription.html', {'form': form})


# ── Déconnexion ────────────────────────────────────────
def vue_deconnexion(request):
    logout(request)
    request.session.flush()
    return redirect('connexion')


# ── Choisir / Switcher de boutique ────────────────────
@login_required
def choisir_boutique(request):
    user = request.user
    profil, _ = ProfilEmploye.objects.get_or_create(user=user)
    if not profil.role:
        profil.role = 'proprietaire'
        profil.save()

    if profil.est_proprietaire:
        boutiques = Boutique.objects.filter(proprietaire=user, est_active=True)
    else:
        # L'employé est directement redirigé sur sa boutique
        if profil.boutique:
            request.session['boutique_active_id'] = profil.boutique.id
            request.session['boutique_active_nom'] = profil.boutique.nom
            return redirect('pos')  # ← Employé → directement à la caisse
        else:
            messages.error(request, "Aucune boutique assignée. Contactez votre responsable.")
            return redirect('deconnexion')

    if request.method == 'POST':
        boutique_id = request.POST.get('boutique_id')
        boutique = boutiques.filter(id=boutique_id).first()
        if boutique:
            request.session['boutique_active_id'] = boutique.id
            request.session['boutique_active_nom'] = boutique.nom
            return redirect('dashboard')  # ← Propriétaire → dashboard
        else:
            messages.error(request, "Accès non autorisé.")

    return render(request, 'stock/choisir_boutique.html', {'boutiques': boutiques})


# ── Créer une boutique ─────────────────────────────────
@login_required
@proprietaire_requis
def creer_boutique(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        adresse = request.POST.get('adresse', '').strip()
        telephone = request.POST.get('telephone', '').strip()

        if nom:
            boutique = Boutique.objects.create(
                nom=nom,
                adresse=adresse,
                telephone=telephone,
                proprietaire=request.user
            )
            request.session['boutique_active_id'] = boutique.id
            request.session['boutique_active_nom'] = boutique.nom
            messages.success(request, f"Boutique « {nom} » créée avec succès !")
            return redirect('dashboard')
        else:
            messages.error(request, "Le nom de la boutique est obligatoire.")

    return render(request, 'stock/creer_boutique.html')


from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth


# ── Dashboard principal ────────────────────────────────
@login_required
@proprietaire_requis
def dashboard(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    aujourd_hui = timezone.now().date()
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    debut_mois = aujourd_hui.replace(day=1)

    # ── Ventes ──────────────────────────────────────
    ventes_all = Vente.objects.filter(boutique=boutique)

    ventes_jour = ventes_all.filter(date_vente__date=aujourd_hui)
    ventes_semaine = ventes_all.filter(date_vente__date__gte=debut_semaine)
    ventes_mois = ventes_all.filter(date_vente__date__gte=debut_mois)

    def calcul_stats(ventes_qs):
        lignes = LigneVente.objects.filter(vente__in=ventes_qs)
        ca = lignes.aggregate(
            total=Sum(F('prix_vente_unitaire') * F('quantite'))
        )['total'] or 0
        benefice = lignes.aggregate(
            total=Sum(
                (F('prix_vente_unitaire') - F('prix_achat_unitaire')) * F('quantite')
            )
        )['total'] or 0
        return {'ca': ca, 'benefice': benefice, 'nb': ventes_qs.count()}

    stats_jour = calcul_stats(ventes_jour)
    stats_semaine = calcul_stats(ventes_semaine)
    stats_mois = calcul_stats(ventes_mois)

    # ── Stock ────────────────────────────────────────
    stocks = StockBoutique.objects.filter(boutique=boutique)
    total_refs = stocks.count()
    total_articles = stocks.aggregate(t=Sum('quantite'))['t'] or 0
    nb_alertes = sum(1 for s in stocks if s.est_sous_seuil)
    valeur_stock = sum(s.valeur_stock for s in stocks)

    # ── Graphique 30 derniers jours ──────────────────
    debut_30j = aujourd_hui - timedelta(days=29)
    ventes_30j = (
        LigneVente.objects
        .filter(vente__boutique=boutique, vente__date_vente__date__gte=debut_30j)
        .annotate(jour=TruncDay('vente__date_vente'))
        .values('jour')
        .annotate(
            ca=Sum(F('prix_vente_unitaire') * F('quantite')),
            benefice=Sum((F('prix_vente_unitaire') - F('prix_achat_unitaire')) * F('quantite'))
        )
        .order_by('jour')
    )

    # Remplir les jours sans vente
    graph_data = {}
    for i in range(30):
        jour = debut_30j + timedelta(days=i)
        graph_data[str(jour)] = {'ca': 0, 'benefice': 0}
    for v in ventes_30j:
        key = str(v['jour'].date())
        graph_data[key] = {
            'ca': float(v['ca'] or 0),
            'benefice': float(v['benefice'] or 0)
        }

    import json as json_module
    graph_labels = json_module.dumps([k[5:] for k in graph_data.keys()])  # MM-DD
    graph_ca = json_module.dumps([v['ca'] for v in graph_data.values()])
    graph_benefice = json_module.dumps([v['benefice'] for v in graph_data.values()])

    # ── Top produits du mois ─────────────────────────
    top_produits = (
        LigneVente.objects
        .filter(vente__boutique=boutique, vente__date_vente__date__gte=debut_mois)
        .values('stock__produit__nom', 'stock__produit__marque__nom')
        .annotate(
            total_qte=Sum('quantite'),
            total_ca=Sum(F('prix_vente_unitaire') * F('quantite')),
            total_benefice=Sum((F('prix_vente_unitaire') - F('prix_achat_unitaire')) * F('quantite'))
        )
        .order_by('-total_qte')[:5]
    )

    # ── Top marques du mois ──────────────────────────
    top_marques = (
        LigneVente.objects
        .filter(vente__boutique=boutique, vente__date_vente__date__gte=debut_mois)
        .values('stock__produit__marque__nom')
        .annotate(total_qte=Sum('quantite'))
        .order_by('-total_qte')[:5]
    )

    # ── Dernières ventes ─────────────────────────────
    dernieres_ventes = (
        ventes_all
        .prefetch_related('lignes')
        .order_by('-date_vente')[:5]
    )

    return render(request, 'stock/dashboard.html', {
        'boutique': boutique,
        'aujourd_hui': aujourd_hui,
        'stats_jour': stats_jour,
        'stats_semaine': stats_semaine,
        'stats_mois': stats_mois,
        'total_refs': total_refs,
        'total_articles': total_articles,
        'nb_alertes': nb_alertes,
        'valeur_stock': valeur_stock,
        'graph_labels': graph_labels,
        'graph_ca': graph_ca,
        'graph_benefice': graph_benefice,
        'top_produits': top_produits,
        'top_marques': top_marques,
        'dernieres_ventes': dernieres_ventes,
    })


# ── Rapport Bénéfices ──────────────────────────────────
@login_required
@proprietaire_requis
def rapport_benefices(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    aujourd_hui = timezone.now().date()
    periode = request.GET.get('periode', 'mois')

    if periode == 'jour':
        debut = aujourd_hui
        titre = f"Aujourd'hui — {aujourd_hui.strftime('%d/%m/%Y')}"
    elif periode == 'semaine':
        debut = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        titre = f"Cette semaine (depuis le {debut.strftime('%d/%m/%Y')})"
    elif periode == 'mois':
        debut = aujourd_hui.replace(day=1)
        titre = aujourd_hui.strftime('%B %Y').capitalize()
    else:  # personnalisé
        debut_str = request.GET.get('debut', str(aujourd_hui.replace(day=1)))
        fin_str = request.GET.get('fin', str(aujourd_hui))
        try:
            debut = date.fromisoformat(debut_str)
            fin = date.fromisoformat(fin_str)
        except ValueError:
            debut = aujourd_hui.replace(day=1)
            fin = aujourd_hui
        titre = f"Du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"

    fin = aujourd_hui if periode != 'personnalise' else fin

    lignes = LigneVente.objects.filter(
        vente__boutique=boutique,
        vente__date_vente__date__gte=debut,
        vente__date_vente__date__lte=fin,
    ).select_related('stock__produit__marque', 'vente')

    # Stats globales
    ca_total = sum(l.montant_total for l in lignes)
    benefice_total = sum(l.benefice for l in lignes)
    nb_ventes = Vente.objects.filter(
        boutique=boutique,
        date_vente__date__gte=debut,
        date_vente__date__lte=fin
    ).count()
    marge = (benefice_total / ca_total * 100) if ca_total else 0

    # Détail par produit
    par_produit = (
        lignes
        .values('stock__produit__nom', 'stock__produit__marque__nom')
        .annotate(
            qte=Sum('quantite'),
            ca=Sum(F('prix_vente_unitaire') * F('quantite')),
            achat=Sum(F('prix_achat_unitaire') * F('quantite')),
            benefice=Sum((F('prix_vente_unitaire') - F('prix_achat_unitaire')) * F('quantite'))
        )
        .order_by('-benefice')
    )

    # Évolution par jour
    par_jour = (
        lignes
        .annotate(jour=TruncDay('vente__date_vente'))
        .values('jour')
        .annotate(
            ca=Sum(F('prix_vente_unitaire') * F('quantite')),
            benefice=Sum((F('prix_vente_unitaire') - F('prix_achat_unitaire')) * F('quantite'))
        )
        .order_by('jour')
    )

    import json as json_module
    graph_labels = json_module.dumps([str(r['jour'].date())[5:] for r in par_jour])
    graph_ca = json_module.dumps([float(r['ca'] or 0) for r in par_jour])
    graph_benefice = json_module.dumps([float(r['benefice'] or 0) for r in par_jour])

    return render(request, 'stock/rapport_benefices.html', {
        'boutique': boutique,
        'titre': titre,
        'periode': periode,
        'debut': debut,
        'fin': fin,
        'ca_total': ca_total,
        'benefice_total': benefice_total,
        'nb_ventes': nb_ventes,
        'marge': marge,
        'par_produit': par_produit,
        'graph_labels': graph_labels,
        'graph_ca': graph_ca,
        'graph_benefice': graph_benefice,
        'aujourd_hui': aujourd_hui,
    })


# ── Rapport Commandes (produits à racheter) ────────────
@login_required
@proprietaire_requis
def rapport_commandes(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    aujourd_hui = timezone.now().date()
    debut_mois = aujourd_hui.replace(day=1)

    stocks = StockBoutique.objects.filter(
        boutique=boutique
    ).select_related('produit__marque', 'produit__categorie')

    # Vitesse de vente (30 derniers jours)
    ventes_30j = (
        LigneVente.objects
        .filter(vente__boutique=boutique, vente__date_vente__date__gte=aujourd_hui - timedelta(days=30))
        .values('stock_id')
        .annotate(total_vendu=Sum('quantite'))
    )
    vitesse_map = {v['stock_id']: v['total_vendu'] for v in ventes_30j}

    # Construire la liste de commande
    a_commander = []
    ok = []
    for stock in stocks:
        vendu_30j = vitesse_map.get(stock.id, 0)
        vitesse_jour = round(vendu_30j / 30, 2)
        # Jours de stock restant
        jours_restants = round(stock.quantite / vitesse_jour) if vitesse_jour > 0 else 999
        qte_suggeree = max(0, vendu_30j - stock.quantite)  # Pour couvrir 30j

        item = {
            'stock': stock,
            'vendu_30j': vendu_30j,
            'vitesse_jour': vitesse_jour,
            'jours_restants': jours_restants,
            'qte_suggeree': max(qte_suggeree, stock.produit.seuil_alerte * 2),
            'urgence': stock.est_sous_seuil,
        }
        if stock.est_sous_seuil or jours_restants < 15:
            a_commander.append(item)
        else:
            ok.append(item)

    a_commander.sort(key=lambda x: (not x['urgence'], x['jours_restants']))

    return render(request, 'stock/rapport_commandes.html', {
        'boutique': boutique,
        'a_commander': a_commander,
        'ok': ok,
        'aujourd_hui': aujourd_hui,
    })

from django.db.models import Q, Sum
from .forms import (
    ProduitForm, StockBoutiqueForm, ArrivageForm,
    SmartphoneIMEIForm, IMEIBulkForm, MarqueForm, CategorieForm
)
from .models import Produit, StockBoutique, SmartphoneIMEI, Marque, Categorie


def get_boutique_active(request):
    """Helper : retourne la boutique active depuis la session."""
    from .models import Boutique
    boutique_id = request.session.get('boutique_active_id')
    if not boutique_id:
        return None
    return Boutique.objects.filter(id=boutique_id).first()


# ── Liste du Stock ─────────────────────────────────────
@login_required
@employe_sa_boutique
def stock_liste(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    stocks = StockBoutique.objects.filter(
        boutique=boutique
    ).select_related('produit', 'produit__marque', 'produit__categorie')

    # Filtres
    q = request.GET.get('q', '')
    marque_id = request.GET.get('marque', '')
    categorie_id = request.GET.get('categorie', '')
    alerte_only = request.GET.get('alerte', '')

    if q:
        stocks = stocks.filter(produit__nom__icontains=q)
    if marque_id:
        stocks = stocks.filter(produit__marque_id=marque_id)
    if categorie_id:
        stocks = stocks.filter(produit__categorie_id=categorie_id)
    if alerte_only:
        # Filtre les produits sous le seuil (on filtre en Python car champ calculé)
        stocks = [s for s in stocks if s.est_sous_seuil]

    # Stats globales
    tous_stocks = StockBoutique.objects.filter(boutique=boutique)
    total_produits = tous_stocks.count()
    total_articles = tous_stocks.aggregate(t=Sum('quantite'))['t'] or 0
    nb_alertes = sum(1 for s in tous_stocks if s.est_sous_seuil)

    marques = Marque.objects.all()
    categories = Categorie.objects.all()

    return render(request, 'stock/stock_liste.html', {
        'stocks': stocks,
        'boutique': boutique,
        'marques': marques,
        'categories': categories,
        'total_produits': total_produits,
        'total_articles': total_articles,
        'nb_alertes': nb_alertes,
        'q': q,
        'marque_id': marque_id,
        'categorie_id': categorie_id,
        'alerte_only': alerte_only,
    })


# ── Ajouter Produit + Stock ────────────────────────────
@login_required
@employe_sa_boutique
def stock_ajouter(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    produit_form = ProduitForm()
    stock_form = StockBoutiqueForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')

        # ── Cas 1 : Produit existant ──────────────────
        if form_type == 'existant':
            produit_existant_id = request.POST.get('produit_existant_id')
            produit = get_object_or_404(Produit, id=produit_existant_id)
            quantite = int(request.POST.get('quantite', 0))
            prix_achat = request.POST.get('prix_achat', 0)
            prix_vente = request.POST.get('prix_vente_suggere', 0)

            stock, created = StockBoutique.objects.get_or_create(
                produit=produit,
                boutique=boutique,
                defaults={
                    'prix_achat': prix_achat,
                    'prix_vente_suggere': prix_vente,
                    'quantite': quantite,
                }
            )
            if not created:
                stock.quantite += quantite
                stock.prix_achat = prix_achat
                stock.prix_vente_suggere = prix_vente
                stock.save()

            messages.success(request, f"Stock mis à jour pour {produit} !")
            return redirect('stock_detail', pk=stock.pk)

        # ── Cas 2 : Nouveau produit ───────────────────
        else:
            produit_form = ProduitForm(request.POST, request.FILES)
            stock_form = StockBoutiqueForm(request.POST)

            if produit_form.is_valid() and stock_form.is_valid():
                produit = produit_form.save()
                stock = stock_form.save(commit=False)
                stock.produit = produit
                stock.boutique = boutique
                stock.save()
                messages.success(request, f"Produit « {produit} » ajouté au stock !")

                if produit.type_produit == 'smartphone':
                    return redirect('imei_ajouter', stock_pk=stock.pk)
                return redirect('stock_liste')
            else:
                messages.error(request, "Corrige les erreurs ci-dessous.")

    produits_existants = Produit.objects.all().order_by('marque__nom', 'nom')
    return render(request, 'stock/stock_ajouter.html', {
        'produit_form': produit_form,
        'stock_form': stock_form,
        'boutique': boutique,
        'produits_existants': produits_existants,
    })

# ── Détail d'un stock ──────────────────────────────────
@login_required
def stock_detail(request, pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=pk, boutique=boutique)
    imeis = stock.imeis.all().order_by('statut', '-date_entree')
    arrivage_form = ArrivageForm(request.POST or None)

    if request.method == 'POST' and arrivage_form.is_valid():
        data = arrivage_form.cleaned_data
        stock.quantite += data['quantite_ajoutee']
        stock.date_dernier_arrivage = data['date_arrivage']

        # Seul le propriétaire peut changer les prix
        est_proprio = request.user.profil.est_proprietaire
        if est_proprio:
            stock.prix_achat = data['nouveau_prix_achat']
            stock.prix_vente_suggere = data['nouveau_prix_vente']

        stock.save()
        messages.success(request, f"{data['quantite_ajoutee']} unité(s) ajoutée(s) au stock !")
        return redirect('stock_detail', pk=pk)

    return render(request, 'stock/stock_detail.html', {
        'stock': stock,
        'imeis': imeis,
        'arrivage_form': arrivage_form,
        'boutique': boutique,
    })


# ── Ajouter des IMEI ──────────────────────────────────
@login_required
def imei_ajouter(request, stock_pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=stock_pk, boutique=boutique)
    form = IMEIBulkForm(request.POST or None)
    erreurs = []
    succes = 0

    if request.method == 'POST' and form.is_valid():
        lignes = form.cleaned_data['imeis'].strip().splitlines()
        couleur = form.cleaned_data.get('couleur', '')
        stockage = form.cleaned_data.get('stockage', '')

        for ligne in lignes:
            imei = ligne.strip()
            if not imei:
                continue
            if len(imei) < 15:
                erreurs.append(f"IMEI invalide (trop court) : {imei}")
                continue
            if SmartphoneIMEI.objects.filter(imei=imei).exists():
                erreurs.append(f"IMEI déjà enregistré : {imei}")
                continue
            SmartphoneIMEI.objects.create(
                stock=stock, imei=imei,
                couleur=couleur, stockage=stockage
            )
            succes += 1

        # Mise à jour de la quantité
        stock.quantite = stock.imeis.filter(statut='disponible').count()
        stock.save()

        if succes:
            messages.success(request, f"{succes} IMEI(s) enregistré(s) avec succès !")
        if erreurs:
            for e in erreurs:
                messages.warning(request, e)

        if not erreurs:
            return redirect('stock_detail', pk=stock_pk)

    return render(request, 'stock/imei_ajouter.html', {
        'form': form,
        'stock': stock,
        'erreurs': erreurs,
    })


# ── Modifier le seuil d'alerte ─────────────────────────
@login_required
def stock_modifier_seuil(request, pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=pk, boutique=boutique)
    if request.method == 'POST':
        seuil = request.POST.get('seuil', '')
        if seuil.isdigit():
            stock.produit.seuil_alerte = int(seuil)
            stock.produit.save()
            messages.success(request, "Seuil d'alerte mis à jour.")
    return redirect('stock_detail', pk=pk)


# ── Supprimer un stock ─────────────────────────────────
@login_required
@proprietaire_requis
def stock_supprimer(request, pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=pk, boutique=boutique)

    # Vérifie si ce stock a des ventes liées
    nb_ventes = stock.lignes_vente.count()

    if request.method == 'POST':
        action = request.POST.get('action')

        if nb_ventes > 0 and action == 'archiver':
            # On ne supprime pas — on met la quantité à 0 et on désactive
            stock.quantite = 0
            stock.produit.seuil_alerte = 0
            stock.produit.save()
            stock.save()
            messages.warning(request, f"« {stock.produit} » archivé (stock à 0). L'historique des ventes est conservé.")
            return redirect('stock_liste')

        elif nb_ventes == 0 and action == 'supprimer':
            nom = str(stock.produit)
            stock.delete()
            messages.success(request, f"« {nom} » supprimé définitivement.")
            return redirect('stock_liste')

    return render(request, 'stock/stock_confirmer_suppression.html', {
        'stock': stock,
        'nb_ventes': nb_ventes,
    })

from .models import Vente, LigneVente
from django.utils import timezone
from django.http import JsonResponse
import json
from decimal import Decimal


# ── POS : Interface de vente ───────────────────────────
@login_required
@employe_sa_boutique
def pos(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    # Tous les stocks disponibles de la boutique
    stocks = StockBoutique.objects.filter(
        boutique=boutique,
        quantite__gt=0
    ).select_related('produit', 'produit__marque', 'produit__categorie')

    # Filtres de recherche produit
    q = request.GET.get('q', '')
    marque_id = request.GET.get('marque', '')
    if q:
        stocks = stocks.filter(produit__nom__icontains=q)
    if marque_id:
        stocks = stocks.filter(produit__marque_id=marque_id)

    marques = Marque.objects.all()

    # Ventes du jour
    aujourd_hui = timezone.now().date()
    ventes_jour = Vente.objects.filter(
        boutique=boutique,
        date_vente__date=aujourd_hui
    ).count()

    return render(request, 'stock/pos.html', {
        'stocks': stocks,
        'boutique': boutique,
        'marques': marques,
        'q': q,
        'marque_id': marque_id,
        'ventes_jour': ventes_jour,
    })


# ── API : IMEI disponibles pour un stock ──────────────
@login_required
def api_imeis_stock(request, stock_pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=stock_pk, boutique=boutique)
    imeis = list(stock.imeis.filter(statut='disponible').values('id', 'imei', 'couleur', 'stockage'))
    return JsonResponse({'imeis': imeis})



# ── Valider une vente ──────────────────────────────────
@login_required
def valider_vente(request):
    if request.method != 'POST':
        return redirect('pos')

    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'erreur': 'Données invalides'}, status=400)

    panier = data.get('panier', [])
    mode_paiement = data.get('mode_paiement', 'especes')
    nom_client = data.get('nom_client', '')
    telephone_client = data.get('telephone_client', '')

    if not panier:
        return JsonResponse({'erreur': 'Le panier est vide'}, status=400)

    # ── Vérifications stock avant de créer la vente ──
    erreurs = []
    for item in panier:
        stock = StockBoutique.objects.filter(
            id=item['stock_id'], boutique=boutique
        ).first()
        if not stock:
            erreurs.append(f"Produit introuvable")
            continue
        if stock.quantite < item['quantite']:
            erreurs.append(
                f"{stock.produit} : stock insuffisant "
                f"(disponible: {stock.quantite}, demandé: {item['quantite']})"
            )

    if erreurs:
        return JsonResponse({'erreurs': erreurs}, status=400)

    # ── Création de la vente ──────────────────────────
    vente = Vente.objects.create(
        boutique=boutique,
        vendeur=request.user,
        mode_paiement=mode_paiement,
        nom_client=nom_client,
        telephone_client=telephone_client,
    )

    for item in panier:
        stock = StockBoutique.objects.get(id=item['stock_id'], boutique=boutique)
        prix_vente = Decimal(str(item['prix_vente']))
        quantite = int(item['quantite'])
        imei_id = item.get('imei_id')

        # Création ligne vente
        ligne = LigneVente.objects.create(
            vente=vente,
            stock=stock,
            quantite=quantite,
            prix_achat_unitaire=stock.prix_achat,
            prix_vente_unitaire=prix_vente,
        )

        # Si IMEI spécifié → marquer comme vendu
        if imei_id:
            imei_obj = SmartphoneIMEI.objects.filter(
                id=imei_id, stock=stock, statut='disponible'
            ).first()
            if imei_obj:
                imei_obj.statut = 'vendu'
                imei_obj.date_vente = timezone.now().date()
                imei_obj.save()
                ligne.imei = imei_obj
                ligne.save()

        # ── Décrémentation du stock ──────────────────
        stock.quantite -= quantite
        stock.save()

    return JsonResponse({
        'succes': True,
        'vente_id': vente.id,
        'reference': str(vente.reference)[:8].upper(),
        'montant_total': float(vente.montant_total),
        'benefice': float(vente.benefice_total),
    })


# ── Reçu / détail d'une vente ─────────────────────────
@login_required
def vente_detail(request, vente_id):
    boutique = get_boutique_active(request)
    vente = get_object_or_404(Vente, id=vente_id, boutique=boutique)
    return render(request, 'stock/vente_succes.html', {
        'vente': vente,
        'boutique': boutique,
    })


# ── Historique des ventes ─────────────────────────────
@login_required
def vente_historique(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    aujourd_hui = timezone.now().date()
    date_str = request.GET.get('date', str(aujourd_hui))

    try:
        from datetime import date
        date_filtre = date.fromisoformat(date_str)
    except ValueError:
        date_filtre = aujourd_hui

    ventes = Vente.objects.filter(
        boutique=boutique,
        date_vente__date=date_filtre
    ).prefetch_related('lignes__stock__produit').order_by('-date_vente')

    # Calculs du jour
    total_ca = sum(v.montant_total for v in ventes)
    total_benefice = sum(v.benefice_total for v in ventes)

    return render(request, 'stock/vente_historique.html', {
        'ventes': ventes,
        'boutique': boutique,
        'date_filtre': date_filtre,
        'aujourd_hui': aujourd_hui,
        'total_ca': total_ca,
        'total_benefice': total_benefice,
    })


# ── Annuler une vente ─────────────────────────────────
@login_required
def vente_annuler(request, vente_id):
    boutique = get_boutique_active(request)
    vente = get_object_or_404(Vente, id=vente_id, boutique=boutique)

    if request.method == 'POST':
        # Restituer le stock
        for ligne in vente.lignes.all():
            ligne.stock.quantite += ligne.quantite
            ligne.stock.save()
            # Remettre l'IMEI disponible si applicable
            if ligne.imei:
                ligne.imei.statut = 'disponible'
                ligne.imei.date_vente = None
                ligne.imei.save()

        vente.delete()
        messages.success(request, "Vente annulée et stock restitué.")
        return redirect('vente_historique')

    return render(request, 'stock/vente_annuler_confirm.html', {'vente': vente})


from django.contrib.auth.models import User


# ── Liste des employés ─────────────────────────────────
@login_required
@proprietaire_requis
def employes_liste(request):
    user = request.user
    # Toutes les boutiques du propriétaire
    boutiques = Boutique.objects.filter(proprietaire=user)
    # Tous les employés de ces boutiques
    employes = ProfilEmploye.objects.filter(
        boutique__in=boutiques,
        role='employe'
    ).select_related('user', 'boutique').order_by('boutique__nom', 'user__username')

    return render(request, 'stock/employes_liste.html', {
        'employes': employes,
        'boutiques': boutiques,
    })


# ── Créer un employé ───────────────────────────────────
@login_required
@proprietaire_requis
def employe_creer(request):
    boutiques = Boutique.objects.filter(proprietaire=request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        nom = request.POST.get('nom', '').strip()
        boutique_id = request.POST.get('boutique_id')
        telephone = request.POST.get('telephone', '').strip()

        # Validations
        if not username or not password or not boutique_id:
            messages.error(request, "Nom d'utilisateur, mot de passe et boutique sont obligatoires.")
            return render(request, 'stock/employe_creer.html', {'boutiques': boutiques})

        if User.objects.filter(username=username).exists():
            messages.error(request, f"Le nom d'utilisateur « {username} » est déjà pris.")
            return render(request, 'stock/employe_creer.html', {'boutiques': boutiques})

        boutique = boutiques.filter(id=boutique_id).first()
        if not boutique:
            messages.error(request, "Boutique invalide.")
            return render(request, 'stock/employe_creer.html', {'boutiques': boutiques})

        # Création User
        employe_user = User.objects.create_user(
            username=username,
            password=password,
            first_name=prenom,
            last_name=nom,
        )

        # Profil employé (le signal l'a créé, on le met à jour)
        profil = employe_user.profil
        profil.role = 'employe'
        profil.boutique = boutique
        profil.telephone = telephone
        profil.save()

        messages.success(request, f"Employé « {username} » créé et assigné à {boutique.nom} !")
        return redirect('employes_liste')

    return render(request, 'stock/employe_creer.html', {'boutiques': boutiques})


# ── Détail / modifier un employé ───────────────────────
@login_required
@proprietaire_requis
def employe_detail(request, employe_id):
    boutiques = Boutique.objects.filter(proprietaire=request.user)
    profil = get_object_or_404(
        ProfilEmploye,
        id=employe_id,
        boutique__in=boutiques,
        role='employe'
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'modifier':
            boutique_id = request.POST.get('boutique_id')
            boutique = boutiques.filter(id=boutique_id).first()
            if boutique:
                profil.boutique = boutique
                profil.telephone = request.POST.get('telephone', '').strip()
                profil.save()
                profil.user.first_name = request.POST.get('prenom', '').strip()
                profil.user.last_name = request.POST.get('nom', '').strip()
                profil.user.save()
                messages.success(request, "Employé mis à jour.")

        elif action == 'reset_password':
            nouveau_mdp = request.POST.get('nouveau_mdp', '').strip()
            if len(nouveau_mdp) >= 4:
                profil.user.set_password(nouveau_mdp)
                profil.user.save()
                messages.success(request, f"Mot de passe de {profil.user.username} réinitialisé.")
            else:
                messages.error(request, "Le mot de passe doit faire au moins 4 caractères.")

        elif action == 'supprimer':
            nom = profil.user.username
            profil.user.delete()
            messages.success(request, f"Employé « {nom} » supprimé.")
            return redirect('employes_liste')

        return redirect('employe_detail', employe_id=employe_id)

    return render(request, 'stock/employe_detail.html', {
        'profil': profil,
        'boutiques': boutiques,
    })
import json as json_module
from .models import DemandeArrivage


# ── EMPLOYÉ : Soumettre un arrivage (sans prix) ────────
@login_required
@employe_sa_boutique
def demande_arrivage(request, stock_pk):
    boutique = get_boutique_active(request)
    stock = get_object_or_404(StockBoutique, pk=stock_pk, boutique=boutique)

    if request.method == 'POST':
        quantite = int(request.POST.get('quantite', 0))
        date_arrivage = request.POST.get('date_arrivage')
        notes = request.POST.get('notes', '')
        imeis_bruts = request.POST.get('imeis', '').strip().splitlines()
        couleur = request.POST.get('couleur', '')
        stockage = request.POST.get('stockage', '')

        if quantite < 1:
            messages.error(request, "La quantité doit être au moins 1.")
            return redirect('stock_detail', pk=stock_pk)

        imeis = []
        for ligne in imeis_bruts:
            imei = ligne.strip()
            if imei:
                imeis.append({'imei': imei, 'couleur': couleur, 'stockage': stockage})

        DemandeArrivage.objects.create(
            boutique=boutique,
            employe=request.user,
            type_demande='arrivage',
            stock=stock,
            quantite=quantite,
            date_arrivage=date_arrivage or None,
            notes=notes,
            imeis_json=json_module.dumps(imeis),
        )

        messages.success(request, "Arrivage soumis ✅ En attente de validation par le responsable.")
        return redirect('stock_liste')

    return render(request, 'stock/demande_arrivage.html', {
        'stock': stock,
        'boutique': boutique,
    })


# ── EMPLOYÉ : Soumettre un nouveau produit ─────────────
@login_required
@employe_sa_boutique
def demande_nouveau_produit(request):
    boutique = get_boutique_active(request)
    marques = Marque.objects.all()
    categories = Categorie.objects.all()

    if request.method == 'POST':
        nom_produit = request.POST.get('nom_produit', '').strip()
        marque_id = request.POST.get('marque_id')
        categorie_id = request.POST.get('categorie_id')
        type_produit = request.POST.get('type_produit', 'smartphone')
        quantite = int(request.POST.get('quantite', 0))
        date_arrivage = request.POST.get('date_arrivage', '')
        notes = request.POST.get('notes', '')
        imeis_bruts = request.POST.get('imeis', '').strip().splitlines()
        couleur = request.POST.get('couleur', '')
        stockage = request.POST.get('stockage', '')

        if not nom_produit or not marque_id or not categorie_id:
            messages.error(request, "Nom, marque et catégorie sont obligatoires.")
            return render(request, 'stock/demande_nouveau_produit.html', {
                'marques': marques, 'categories': categories, 'boutique': boutique
            })

        imeis = []
        for ligne in imeis_bruts:
            imei = ligne.strip()
            if imei:
                imeis.append({'imei': imei, 'couleur': couleur, 'stockage': stockage})

        DemandeArrivage.objects.create(
            boutique=boutique,
            employe=request.user,
            type_demande='nouveau_produit',
            nom_produit=nom_produit,
            marque_id=marque_id,
            categorie_id=categorie_id,
            type_produit=type_produit,
            quantite=quantite,
            date_arrivage=date_arrivage or None,
            notes=notes,
            imeis_json=json_module.dumps(imeis),
        )

        messages.success(request, "Nouveau produit soumis ✅ En attente de validation.")
        return redirect('stock_liste')

    return render(request, 'stock/demande_nouveau_produit.html', {
        'marques': marques,
        'categories': categories,
        'boutique': boutique,
    })


# ── PATRON : Liste des demandes en attente ─────────────
@login_required
@proprietaire_requis
def demandes_liste(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    boutiques = Boutique.objects.filter(proprietaire=request.user)
    demandes_attente = DemandeArrivage.objects.filter(
        boutique__in=boutiques,
        statut='en_attente'
    ).select_related('employe', 'boutique', 'stock__produit', 'marque', 'categorie')

    demandes_traitees = DemandeArrivage.objects.filter(
        boutique__in=boutiques,
        statut__in=['confirme', 'refuse']
    ).select_related('employe', 'boutique').order_by('-date_traitement')[:20]

    return render(request, 'stock/demandes_liste.html', {
        'demandes_attente': demandes_attente,
        'demandes_traitees': demandes_traitees,
        'nb_attente': demandes_attente.count(),
    })


# ── PATRON : Confirmer ou refuser une demande ──────────
@login_required
@proprietaire_requis
def demande_traiter(request, demande_id):
    boutiques = Boutique.objects.filter(proprietaire=request.user)
    demande = get_object_or_404(DemandeArrivage, id=demande_id, boutique__in=boutiques)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'refuser':
            demande.statut = 'refuse'
            demande.notes_patron = request.POST.get('notes_patron', '')
            demande.date_traitement = timezone.now()
            demande.save()
            messages.warning(request, "Demande refusée.")
            return redirect('demandes_liste')

        if action == 'confirmer':
            prix_achat = request.POST.get('prix_achat', '').strip()
            prix_vente = request.POST.get('prix_vente_suggere', '').strip()

            if not prix_achat or not prix_vente:
                messages.error(request, "Prix d'achat et prix de vente sont obligatoires.")
                return redirect('demande_traiter', demande_id=demande_id)

            prix_achat = float(prix_achat)
            prix_vente = float(prix_vente)

            # ── Arrivage produit existant ────────────
            if demande.type_demande == 'arrivage' and demande.stock:
                stock = demande.stock
                stock.quantite += demande.quantite
                stock.prix_achat = prix_achat
                stock.prix_vente_suggere = prix_vente
                if demande.date_arrivage:
                    stock.date_dernier_arrivage = demande.date_arrivage
                stock.save()

                for item in demande.imeis_list:
                    imei_code = item.get('imei', '').strip()
                    if imei_code and not SmartphoneIMEI.objects.filter(imei=imei_code).exists():
                        SmartphoneIMEI.objects.create(
                            stock=stock,
                            imei=imei_code,
                            couleur=item.get('couleur', ''),
                            stockage=item.get('stockage', ''),
                        )

            # ── Nouveau produit ───────────────────────
            elif demande.type_demande == 'nouveau_produit':
                produit, _ = Produit.objects.get_or_create(
                    nom=demande.nom_produit,
                    marque=demande.marque,
                    defaults={
                        'categorie': demande.categorie,
                        'type_produit': demande.type_produit or 'smartphone',
                    }
                )
                stock, created = StockBoutique.objects.get_or_create(
                    produit=produit,
                    boutique=demande.boutique,
                    defaults={
                        'prix_achat': prix_achat,
                        'prix_vente_suggere': prix_vente,
                        'quantite': 0,
                    }
                )
                if not created:
                    stock.prix_achat = prix_achat
                    stock.prix_vente_suggere = prix_vente

                stock.quantite += demande.quantite
                if demande.date_arrivage:
                    stock.date_dernier_arrivage = demande.date_arrivage
                stock.save()

                for item in demande.imeis_list:
                    imei_code = item.get('imei', '').strip()
                    if imei_code and not SmartphoneIMEI.objects.filter(imei=imei_code).exists():
                        SmartphoneIMEI.objects.create(
                            stock=stock,
                            imei=imei_code,
                            couleur=item.get('couleur', ''),
                            stockage=item.get('stockage', ''),
                        )

            demande.prix_achat = prix_achat
            demande.prix_vente_suggere = prix_vente
            demande.notes_patron = request.POST.get('notes_patron', '')
            demande.statut = 'confirme'
            demande.date_traitement = timezone.now()
            demande.save()

            messages.success(request, "✅ Arrivage confirmé et stock mis à jour !")
            return redirect('demandes_liste')

    return render(request, 'stock/demande_traiter.html', {
        'demande': demande,
    })

from .models import Depense


@login_required
def depenses_liste(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    aujourd_hui = timezone.now().date()
    date_str = request.GET.get('date', str(aujourd_hui))
    try:
        from datetime import date as date_type
        date_filtre = date_type.fromisoformat(date_str)
    except ValueError:
        date_filtre = aujourd_hui

    # Ventes du jour
    ventes = Vente.objects.filter(
        boutique=boutique,
        date_vente__date=date_filtre
    ).prefetch_related('lignes').order_by('date_vente')

    # Dépenses du jour
    depenses = Depense.objects.filter(
        boutique=boutique,
        date_depense__date=date_filtre
    ).select_related('enregistre_par').order_by('date_depense')

    # Calculs
    total_ca = sum(v.montant_total for v in ventes)
    total_benefice_brut = sum(v.benefice_total for v in ventes)
    total_depenses = sum(d.montant for d in depenses)
    benefice_net = total_benefice_brut - total_depenses

    # Fusionner ventes + dépenses dans un seul flux chronologique
    flux = []
    for v in ventes:
        flux.append({
            'type': 'vente',
            'heure': v.date_vente,
            'obj': v,
        })
    for d in depenses:
        flux.append({
            'type': 'depense',
            'heure': d.date_depense,
            'obj': d,
        })
    flux.sort(key=lambda x: x['heure'])

    return render(request, 'stock/depenses_liste.html', {
        'boutique': boutique,
        'flux': flux,
        'date_filtre': date_filtre,
        'aujourd_hui': aujourd_hui,
        'total_ca': total_ca,
        'total_benefice_brut': total_benefice_brut,
        'total_depenses': total_depenses,
        'benefice_net': benefice_net,
        'nb_ventes': ventes.count(),
        'nb_depenses': depenses.count(),
    })


@login_required
def depense_ajouter(request):
    boutique = get_boutique_active(request)
    if not boutique:
        return redirect('choisir_boutique')

    if request.method == 'POST':
        montant = request.POST.get('montant', '').strip()
        motif = request.POST.get('motif', '').strip()

        if not montant or not motif:
            messages.error(request, "Montant et motif sont obligatoires.")
        else:
            try:
                montant_val = float(montant)
                if montant_val <= 0:
                    raise ValueError
            except ValueError:
                messages.error(request, "Montant invalide.")
                return redirect('depense_ajouter')

            Depense.objects.create(
                boutique=boutique,
                enregistre_par=request.user,
                montant=montant_val,
                motif=motif,
            )
            messages.success(request, f"Dépense de {montant_val:,.0f} F enregistrée.")
            return redirect('depenses_liste')

    return render(request, 'stock/depense_ajouter.html', {'boutique': boutique})


@login_required
def depense_supprimer(request, depense_id):
    boutique = get_boutique_active(request)
    depense = get_object_or_404(Depense, id=depense_id, boutique=boutique)

    if not request.user.profil.est_proprietaire and depense.enregistre_par != request.user:
        messages.error(request, "Action non autorisée.")
        return redirect('depenses_liste')

    if request.method == 'POST':
        depense.delete()
        messages.success(request, "Dépense supprimée.")
        return redirect('depenses_liste')

    return render(request, 'stock/depense_supprimer_confirm.html', {'depense': depense})