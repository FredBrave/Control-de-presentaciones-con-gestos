from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from .forms import CustomUserCreationForm
from django.contrib.auth import get_user_model                    
User = get_user_model()

def registerPage(request):
    form = CustomUserCreationForm()
    if request.method == 'POST':
        data = request.POST.copy()

        if 'password1' in data and 'password2' not in data:
            data['password2'] = data['password1']

        email = data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            messages.error(request, 'El correo ya está en uso')
        else:  
            form = CustomUserCreationForm(data)
            if form.is_valid():
                user = form.save(commit=False)
                user.username = user.username.lower()
                user.save()
                login(request, user)
                return redirect('home')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)

    return render(request, 'seguridad/register.html', {'form': form})

def loginPage(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            messages.error(request, "Usuario o contraseña incorrectos")
            return render(request, "seguridad/login.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")  
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, "seguridad/login.html")

def home(request):
    return render(request, 'presentaciones/home.html')
