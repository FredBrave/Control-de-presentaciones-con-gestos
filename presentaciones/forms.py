from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'email', 'password1', 'password2']


class UploadPresentationForm(forms.Form):
    titulo = forms.CharField(
        label="Título",
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nombre de la presentación'
        })
    )
    archivo = forms.FileField(
        label="Archivo",
        required=True,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 
            'accept': '.pdf,.pptx'
        })
    )
    ubicacion = forms.ChoiceField(
        label="Ubicación de almacenamiento",
        choices=[
            ('drive', 'Google Drive'),
            ('local', 'Servidor Local')
        ],
        initial='drive',
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )