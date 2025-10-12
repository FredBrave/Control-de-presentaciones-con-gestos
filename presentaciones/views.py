from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from .forms import CustomUserCreationForm

def registerPage(request):
    form = CustomUserCreationForm()
    if request.method == 'POST':
        data = request.POST.copy()

        if 'password1' in data and 'password2' not in data:
            data['password2'] = data['password1']

        form = CustomUserCreationForm(data)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Ocurrió un error durante el registro')

    return render(request, 'seguridad/register.html', {'form': form})

def loginPage(request):
    return render(request, 'seguridad/login.html')

def home(request):
    return render(request, 'presentaciones/home.html')
