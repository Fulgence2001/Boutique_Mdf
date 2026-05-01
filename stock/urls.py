from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.vue_connexion, name='connexion'),
    path('inscription/', views.vue_inscription, name='inscription'),
    path('deconnexion/', views.vue_deconnexion, name='deconnexion'),

    # Boutiques
    path('boutiques/', views.choisir_boutique, name='choisir_boutique'),
    path('boutiques/creer/', views.creer_boutique, name='creer_boutique'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Stock
    path('stock/', views.stock_liste, name='stock_liste'),
    path('stock/ajouter/', views.stock_ajouter, name='stock_ajouter'),
    path('stock/<int:pk>/', views.stock_detail, name='stock_detail'),
    path('stock/<int:pk>/seuil/', views.stock_modifier_seuil, name='stock_modifier_seuil'),
    path('stock/<int:pk>/supprimer/', views.stock_supprimer, name='stock_supprimer'),
    path('stock/<int:stock_pk>/imei/', views.imei_ajouter, name='imei_ajouter'),

    # Ventes POS
    path('pos/', views.pos, name='pos'),
    path('pos/valider/', views.valider_vente, name='valider_vente'),
    path('pos/api/imeis/<int:stock_pk>/', views.api_imeis_stock, name='api_imeis_stock'),
    path('ventes/', views.vente_historique, name='vente_historique'),
    path('ventes/<int:vente_id>/', views.vente_detail, name='vente_detail'),
    path('ventes/<int:vente_id>/annuler/', views.vente_annuler, name='vente_annuler'),

    # Rapports
    path('dashboard/', views.dashboard, name='dashboard'),
    path('rapports/benefices/', views.rapport_benefices, name='rapport_benefices'),
    path('rapports/commandes/', views.rapport_commandes, name='rapport_commandes'),

    # Gestion employés
    path('employes/', views.employes_liste, name='employes_liste'),
    path('employes/creer/', views.employe_creer, name='employe_creer'),
    path('employes/<int:employe_id>/', views.employe_detail, name='employe_detail'),

    # Demandes arrivage
    path('demandes/', views.demandes_liste, name='demandes_liste'),
    path('demandes/<int:demande_id>/', views.demande_traiter, name='demande_traiter'),
    path('stock/<int:stock_pk>/demande-arrivage/', views.demande_arrivage, name='demande_arrivage'),
    path('stock/demande-nouveau-produit/', views.demande_nouveau_produit, name='demande_nouveau_produit'),
]