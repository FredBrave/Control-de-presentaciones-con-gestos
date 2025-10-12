from . import views
from django.urls import path


urlpatterns = [
    path('login/', views.loginPage, name='login'),
    path('register/', views.registerPage, name='register'),
  #  path('logout/', views.logoutUser, name='logout'),
    path('', views.home, name='home')
]