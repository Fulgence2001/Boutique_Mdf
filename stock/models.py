from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid


# ──────────────────────────────────────────
# 1. BOUTIQUE
# ──────────────────────────────────────────
class Boutique(models.Model):
    """Une boutique appartient à un propriétaire (User)."""
    nom = models.CharField(max_length=100)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    proprietaire = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='boutiques'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    est_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Boutique"
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ──────────────────────────────────────────
# 2. PROFIL EMPLOYÉ (extension de User)
# ──────────────────────────────────────────
class ProfilEmploye(models.Model):
    """Lie un User Django à une boutique spécifique."""
    ROLE_CHOICES = [
        ('proprietaire', 'Propriétaire'),
        ('employe', 'Employé'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    boutique = models.ForeignKey(
        Boutique,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employes'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employe')
    telephone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def est_proprietaire(self):
        return self.role == 'proprietaire'


# ──────────────────────────────────────────
# 3. CATÉGORIE ET MARQUE
# ──────────────────────────────────────────
class Marque(models.Model):
    """Ex: Samsung, Infinix, Tecno, Xiaomi..."""
    nom = models.CharField(max_length=50, unique=True)
    logo = models.ImageField(upload_to='marques/', blank=True, null=True)

    def __str__(self):
        return self.nom


class Categorie(models.Model):
    """Ex: Smartphone, Accessoire, Tablette..."""
    nom = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nom


# ──────────────────────────────────────────
# 4. PRODUIT (générique)
# ──────────────────────────────────────────
class Produit(models.Model):
    """Modèle de produit — le "catalogue" (ex: Infinix Hot 40)."""
    TYPE_CHOICES = [
        ('smartphone', 'Smartphone'),
        ('accessoire', 'Accessoire'),
        ('tablette', 'Tablette'),
        ('autre', 'Autre'),
    ]
    nom = models.CharField(max_length=200)
    marque = models.ForeignKey(Marque, on_delete=models.PROTECT, related_name='produits')
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name='produits')
    type_produit = models.CharField(max_length=20, choices=TYPE_CHOICES, default='smartphone')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='produits/', blank=True, null=True)

    # Seuil d'alerte stock
    seuil_alerte = models.PositiveIntegerField(
        default=3,
        help_text="Alerte si le stock tombe en dessous de ce seuil"
    )

    class Meta:
        verbose_name = "Produit"
        ordering = ['marque__nom', 'nom']

    def __str__(self):
        return f"{self.marque} {self.nom}"

# ──────────────────────────────────────────
# 5. STOCK PAR BOUTIQUE
# ──────────────────────────────────────────
class StockBoutique(models.Model):
    """
    Représente l'inventaire d'UN produit dans UNE boutique.
    C'est ici qu'on gère les prix d'achat et les quantités.
    """
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='stocks')
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='stocks')
    quantite = models.PositiveIntegerField(default=0)
    prix_achat = models.DecimalField(
        max_digits=10, decimal_places=0,
        validators=[MinValueValidator(0)],
        help_text="Prix d'achat moyen en FCFA"
    )
    prix_vente_suggere = models.DecimalField(
        max_digits=10, decimal_places=0,
        validators=[MinValueValidator(0)],
        help_text="Prix conseillé au vendeur"
    )
    date_dernier_arrivage = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('produit', 'boutique')
        verbose_name = "Stock Boutique"

    def __str__(self):
        return f"{self.produit} | {self.boutique.nom} | Qté: {self.quantite}"

    @property
    def est_sous_seuil(self):
        return self.quantite <= self.produit.seuil_alerte

    @property
    def valeur_stock(self):
        return self.quantite * self.prix_achat


# ──────────────────────────────────────────
# 6. SMARTPHONE AVEC IMEI (cas spécial)
# ──────────────────────────────────────────
class SmartphoneIMEI(models.Model):
    """
    Chaque smartphone physique a un IMEI unique.
    Permet le suivi unitaire (vendu ou disponible).
    """
    STATUT_CHOICES = [
        ('disponible', 'Disponible'),
        ('vendu', 'Vendu'),
        ('defectueux', 'Défectueux'),
        ('retour', 'Retour SAV'),
    ]
    stock = models.ForeignKey(StockBoutique, on_delete=models.CASCADE, related_name='imeis')
    imei = models.CharField(max_length=17, unique=True)
    couleur = models.CharField(max_length=50, blank=True)
    stockage = models.CharField(max_length=20, blank=True, help_text="Ex: 128GB, 256GB")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='disponible')
    date_entree = models.DateField(auto_now_add=True)
    date_vente = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Smartphone (IMEI)"

    def __str__(self):
        return f"{self.stock.produit} | IMEI: {self.imei} | {self.get_statut_display()}"


# ──────────────────────────────────────────
# 7. VENTE
# ──────────────────────────────────────────
class Vente(models.Model):
    """Enregistre une transaction complète."""
    PAIEMENT_CHOICES = [
        ('especes', 'Espèces'),
        ('mobile_money', 'Mobile Money'),
        ('virement', 'Virement'),
        ('credit', 'Crédit'),
    ]
    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    boutique = models.ForeignKey(Boutique, on_delete=models.PROTECT, related_name='ventes')
    vendeur = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventes')
    date_vente = models.DateTimeField(auto_now_add=True)
    mode_paiement = models.CharField(max_length=20, choices=PAIEMENT_CHOICES, default='especes')
    nom_client = models.CharField(max_length=100, blank=True)
    telephone_client = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vente"
        ordering = ['-date_vente']

    def __str__(self):
        return f"Vente #{str(self.reference)[:8]} | {self.boutique.nom} | {self.date_vente.strftime('%d/%m/%Y')}"

    @property
    def montant_total(self):
        return sum(ligne.montant_total for ligne in self.lignes.all())

    @property
    def benefice_total(self):
        return sum(ligne.benefice for ligne in self.lignes.all())


class LigneVente(models.Model):
    """
    Une ligne dans une vente.
    Capture le prix d'achat ET le prix de vente négocié au moment de la vente.
    """
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name='lignes')
    stock = models.ForeignKey(StockBoutique, on_delete=models.PROTECT, related_name='lignes_vente')
    imei = models.OneToOneField(
        SmartphoneIMEI,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ligne_vente'
    )
    quantite = models.PositiveIntegerField(default=1)

    # Prix figés au moment de la vente (crucial pour les rapports financiers !)
    prix_achat_unitaire = models.DecimalField(max_digits=10, decimal_places=0)
    prix_vente_unitaire = models.DecimalField(max_digits=10, decimal_places=0)

    class Meta:
        verbose_name = "Ligne de Vente"

    def __str__(self):
        return f"{self.stock.produit} x{self.quantite}"

    @property
    def montant_total(self):
        return self.quantite * self.prix_vente_unitaire

    @property
    def benefice(self):
        return self.quantite * (self.prix_vente_unitaire - self.prix_achat_unitaire)
    
class DemandeArrivage(models.Model):
    """
    Créée par l'employé — doit être confirmée par le propriétaire
    qui y ajoute le prix d'achat.
    """
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('confirme', 'Confirmé'),
        ('refuse', 'Refusé'),
    ]
    TYPE_CHOICES = [
        ('arrivage', 'Arrivage stock existant'),
        ('nouveau_produit', 'Nouveau produit'),
    ]

    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='demandes')
    employe = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes')
    type_demande = models.CharField(max_length=20, choices=TYPE_CHOICES, default='arrivage')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    # Produit existant (arrivage)
    stock = models.ForeignKey(
        StockBoutique, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes'
    )

    # Nouveau produit
    nom_produit = models.CharField(max_length=200, blank=True)
    marque = models.ForeignKey(
        Marque, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    categorie = models.ForeignKey(
        Categorie, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    type_produit = models.CharField(max_length=20, blank=True)

    # Infos communes
    quantite = models.PositiveIntegerField(default=0)
    date_arrivage = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # IMEI (stockés en JSON : liste de dicts)
    imeis_json = models.TextField(blank=True, default='[]')

    # Rempli par le propriétaire à la confirmation
    prix_achat = models.DecimalField(
        max_digits=10, decimal_places=0,
        null=True, blank=True
    )
    prix_vente_suggere = models.DecimalField(
        max_digits=10, decimal_places=0,
        null=True, blank=True
    )
    notes_patron = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Demande d'arrivage"

    def __str__(self):
        return f"{self.get_type_demande_display()} — {self.boutique.nom} — {self.get_statut_display()}"

    @property
    def imeis_list(self):
        import json
        try:
            return json.loads(self.imeis_json)
        except Exception:
            return []

class Depense(models.Model):
    boutique = models.ForeignKey(
        Boutique, on_delete=models.CASCADE, related_name='depenses'
    )
    enregistre_par = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='depenses'
    )
    montant = models.DecimalField(max_digits=10, decimal_places=0)
    motif = models.CharField(
        max_length=255,
        help_text="Ex: Patron a pris 50.000F, Remis à Kofi pour transport..."
    )
    date_depense = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_depense']
        verbose_name = "Dépense"

    def __str__(self):
        return f"{self.motif} — {self.montant} F"