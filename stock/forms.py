from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import ProfilEmploye, Boutique
from django.contrib.auth.models import User


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={'placeholder': "Nom d'utilisateur", 'autofocus': True})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'placeholder': "Mot de passe"})
    )


class InscriptionForm(forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput())
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return 
from .models import Produit, StockBoutique, SmartphoneIMEI, Marque, Categorie

class MarqueForm(forms.ModelForm):
    class Meta:
        model = Marque
        fields = ['nom']
        widgets = {'nom': forms.TextInput(attrs={'placeholder': 'Ex: Infinix'})}


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nom']
        widgets = {'nom': forms.TextInput(attrs={'placeholder': 'Ex: Smartphone'})}


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['nom', 'marque', 'categorie', 'type_produit', 'description', 'image', 'seuil_alerte']
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Ex: Hot 40 Pro'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Description optionnelle...'}),
            'seuil_alerte': forms.NumberInput(attrs={'min': 1}),
        }

class StockBoutiqueForm(forms.ModelForm):
    class Meta:
        model = StockBoutique
        fields = ['quantite', 'prix_achat', 'prix_vente_suggere', 'date_dernier_arrivage']
        widgets = {
            'quantite': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Ex: 10'}),
            'prix_achat': forms.NumberInput(attrs={'placeholder': 'Ex: 85000'}),
            'prix_vente_suggere': forms.NumberInput(attrs={'placeholder': 'Ex: 95000'}),
            'date_dernier_arrivage': forms.DateInput(attrs={'type': 'date'}),
        }


class ArrivageForm(forms.Form):
    quantite_ajoutee = forms.IntegerField(
        min_value=1,
        label="Quantité reçue",
        widget=forms.NumberInput(attrs={'placeholder': 'Ex: 10'})
    )
    nouveau_prix_achat = forms.DecimalField(
        max_digits=10, decimal_places=0,
        label="Nouveau prix d'achat (FCFA)",
        required=False,   # ← optionnel pour l'employé
        widget=forms.NumberInput(attrs={'placeholder': 'Ex: 83000'})
    )
    nouveau_prix_vente = forms.DecimalField(
        max_digits=10, decimal_places=0,
        label="Nouveau prix de vente conseillé (FCFA)",
        required=False,   # ← optionnel pour l'employé
        widget=forms.NumberInput(attrs={'placeholder': 'Ex: 95000'})
    )
    date_arrivage = forms.DateField(
        label="Date d'arrivage",
        widget=forms.DateInput(attrs={'type': 'date'})
    )


class SmartphoneIMEIForm(forms.ModelForm):
    class Meta:
        model = SmartphoneIMEI
        fields = ['imei', 'couleur', 'stockage', 'statut']
        widgets = {
            'imei': forms.TextInput(attrs={'placeholder': '15 chiffres', 'maxlength': 17}),
            'couleur': forms.TextInput(attrs={'placeholder': 'Ex: Noir, Doré'}),
            'stockage': forms.TextInput(attrs={'placeholder': 'Ex: 128GB'}),
        }


class IMEIBulkForm(forms.Form):
    """Saisie de plusieurs IMEI d'un coup (un par ligne)."""
    imeis = forms.CharField(
        label="IMEI (un par ligne)",
        widget=forms.Textarea(attrs={
            'rows': 8,
            'placeholder': '351234567890001\n351234567890002\n351234567890003'
        })
    )
    couleur = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Noir'})
    )
    stockage = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: 128GB'})
    )