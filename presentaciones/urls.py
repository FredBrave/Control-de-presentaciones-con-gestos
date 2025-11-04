from . import views
from django.urls import path

app_name = 'presentaciones'

urlpatterns = [
    path('login/', views.loginPage, name='login'),
    path('register/', views.registerPage, name='register'),
    path('logout/', views.logoutUser, name='logout'),
    path('', views.home, name='home'),
    path('upload/', views.uploadPage, name='upload'),
    path('eliminar/<int:presentacion_id>/', views.eliminar_presentacion, name='eliminar'),
    path('import-google-slides/', views.import_from_google_slides, name='import_from_google_slides'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path('select-presentations/', views.select_presentations, name='select_presentations'),
    path('import-selected-presentations/', views.import_selected_presentations, name='import_selected_presentations'),
    path('presentar/<int:presentacion_id>/', views.presentar, name='presentar'),
    path('detector/iniciar/', views.iniciar_detector, name='iniciar_detector'),
    path('detector/detener/', views.detener_detector, name='detener_detector'),
    path('detector/estado/', views.verificar_estado_detector, name='verificar_estado_detector'),
    path('comando-gesto/', views.comando_gesto, name='comando_gesto'),
]