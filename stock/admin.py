from django.contrib import admin
from .models import (
    Boutique, ProfilEmploye, Marque, Categorie,
    Produit, StockBoutique, SmartphoneIMEI, Vente, LigneVente
)

admin.site.register(Boutique)
admin.site.register(ProfilEmploye)
admin.site.register(Marque)
admin.site.register(Categorie)
admin.site.register(Produit)
admin.site.register(StockBoutique)
admin.site.register(SmartphoneIMEI)

class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0

@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    inlines = [LigneVenteInline]
    list_display = ['reference', 'boutique', 'vendeur', 'date_vente', 'mode_paiement']