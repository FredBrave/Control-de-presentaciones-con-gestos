from django.shortcuts import render, redirect
import os
import traceback
import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .forms import CustomUserCreationForm
from django.contrib.auth import get_user_model
from google.oauth2 import service_account
from django.core.files import File
from .google_drive_oauth import get_or_create_user_folder, upload_to_drive
from googleapiclient.discovery import build
import tempfile
from googleapiclient.errors import HttpError
from django.urls import reverse
import time
from .models import Presentacion
from django.contrib.auth.decorators import login_required
from .forms import UploadPresentationForm
from .google_slides_import import (
    get_authorization_url, 
    get_credentials_from_code,
    get_user_presentations,
    copy_presentation_to_drive
)

logger = logging.getLogger(__name__)



User = get_user_model()

def safe_remove(path, retries=3, delay=1):
    for i in range(retries):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            time.sleep(delay)


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

@login_required
def logoutUser(request):
    logout(request)
    return redirect('login')

@login_required
def home(request):
    presentaciones = Presentacion.objects.filter(usuario=request.user).order_by('-fecha_subida')[:10]

    context = {
        'presentaciones': presentaciones
    }
    return render(request, 'presentaciones/home.html', context)

logger = logging.getLogger(__name__)

@login_required
def uploadPage(request):
    if request.method == 'POST':
        form = UploadPresentationForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            file = form.cleaned_data['archivo']
            titulo = form.cleaned_data['titulo']
            ubicacion = form.cleaned_data['ubicacion']
            filename = file.name
            ext = os.path.splitext(filename)[1].lower()

            tmp_path = None
            pdf_path = None

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    for chunk in file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                upload_path = tmp_path
                upload_name = filename
                mimetype = file.content_type

                if ext == '.pptx':
                    if os.name != 'nt':
                        messages.error(request, 'La conversión de PPTX a PDF solo está disponible en Windows.')
                        return redirect('upload')
                    
                    try:
                        import comtypes.client
                        pdf_path = tmp_path.replace('.pptx', '.pdf')
                        powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
                        powerpoint.Visible = 0
                        
                        try:
                            presentation = powerpoint.Presentations.Open(tmp_path, WithWindow=False)
                            presentation.SaveAs(pdf_path, 32)
                            presentation.Close()
                        finally:
                            powerpoint.Quit()

                        upload_path = pdf_path
                        upload_name = filename.replace('.pptx', '.pdf')
                        mimetype = 'application/pdf'
                        
                    except Exception as e:
                        logger.error(f"Error al convertir PPTX: {e}")
                        messages.error(request, 'Error al convertir el archivo PPTX a PDF.')
                        return redirect('upload')

                if not upload_name.lower().endswith('.pdf'):
                    messages.error(request, 'Solo se permiten archivos PDF o PPTX.')
                    return redirect('upload')

                if ubicacion == 'drive':
                    
                    folder_id = get_or_create_user_folder(user)
                    if not folder_id:
                        raise Exception("No se pudo obtener o crear la carpeta en Drive.")

                    datos_drive = upload_to_drive(upload_path, upload_name, folder_id)

                    presentacion = Presentacion.objects.create(
                        usuario=user,
                        nombre=datos_drive['name'],
                        titulo=titulo,
                        drive_id=datos_drive['id'],
                        enlace_drive=datos_drive.get('webViewLink', ''),
                        ubicacion='drive'
                    )
                    
                    messages.success(request, f'✓ Presentación "{titulo}" subida correctamente a Google Drive.')
                
                else:
                    presentacion = Presentacion.objects.create(
                        usuario=user,
                        nombre=upload_name,
                        titulo=titulo,
                        ubicacion='local'
                    )
                    
                    with open(upload_path, 'rb') as f:
                        presentacion.archivo_local.save(upload_name, File(f), save=False)
                    
                    messages.success(request, f'✓ Presentación "{titulo}" guardada correctamente en el servidor.')

                try:
                    presentacion.generar_miniatura()
                except Exception as e:
                    logger.warning(f"Error al generar miniatura: {e}")
                
                presentacion.save()

                return redirect('home')

            except Exception as e:
                error_traceback = traceback.format_exc()
                logger.error(f"Error durante la subida para {user.username}: {e}")
                logger.error(error_traceback)
                messages.error(request, f'Ocurrió un error al procesar tu archivo: {str(e)}')
                return redirect('upload')

            finally:
                if tmp_path:
                    safe_remove(tmp_path)
                if pdf_path and pdf_path != tmp_path:
                    safe_remove(pdf_path)

        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UploadPresentationForm()

    return render(request, 'presentaciones/upload.html', {'form': form})


@login_required
def import_from_google_slides(request):
    redirect_uri = request.build_absolute_uri(reverse('oauth2callback'))
    
    try:
        authorization_url, state = get_authorization_url(redirect_uri)
        request.session['oauth_state'] = state
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error al iniciar OAuth: {e}")
        messages.error(request, 'Error al conectar con Google. Verifica tu configuración.')
        return redirect('home')

@login_required
def oauth2callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'Error de autorización: {error}')
        return redirect('home')
    
    session_state = request.session.get('oauth_state')
    if not state or state != session_state:
        messages.error(request, 'Error de seguridad. Intenta nuevamente.')
        return redirect('home')
    
    try:
        redirect_uri = request.build_absolute_uri(reverse('oauth2callback'))
        credentials_dict = get_credentials_from_code(code, state, redirect_uri)
        
        request.session['google_credentials'] = credentials_dict
        
        return redirect('select_presentations')
        
    except Exception as e:
        logger.error(f"Error en OAuth callback: {e}")
        messages.error(request, 'Error al procesar la autorización.')
        return redirect('home')


@login_required
def select_presentations(request):
    credentials_dict = request.session.get('google_credentials')
    
    if not credentials_dict:
        messages.error(request, 'Sesión expirada. Por favor, autoriza nuevamente.')
        return redirect('import_from_google_slides')
    
    try:
        presentations = get_user_presentations(credentials_dict)
        
        context = {
            'presentations': presentations
        }
        
        return render(request, 'presentaciones/select_presentations.html', context)
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Error al obtener presentaciones: {e}")
        logger.error(error_traceback)
        messages.error(request, f'Error al obtener tus presentaciones de Google Slides: {str(e)}')
        return redirect('home')


@login_required
def import_selected_presentations(request):
    if request.method != 'POST':
        return redirect('select_presentations')
    
    credentials_dict = request.session.get('google_credentials')
    
    if not credentials_dict:
        messages.error(request, 'Sesión expirada. Por favor, autoriza nuevamente.')
        return redirect('import_from_google_slides')
    
    selected_ids = request.POST.getlist('presentations')
    
    if not selected_ids:
        messages.warning(request, 'No seleccionaste ninguna presentación.')
        return redirect('select_presentations')
    
    try:
        folder_id = get_or_create_user_folder(request.user)
        
        if not folder_id:
            raise Exception("No se pudo obtener la carpeta del usuario.")
        
        imported_count = 0
        errores = []
        presentations = get_user_presentations(credentials_dict)
        presentations_dict = {p['id']: p for p in presentations}
        
        for presentation_id in selected_ids:
            try:
                copied_data = copy_presentation_to_drive(
                    presentation_id, 
                    folder_id, 
                    credentials_dict
                )
                
                if not Presentacion.objects.filter(
                    usuario=request.user, 
                    drive_id=copied_data['id']
                ).exists():

                    thumbnail_url = None
                    if presentation_id in presentations_dict:
                        thumbnail_url = presentations_dict[presentation_id].get('thumbnailLink')
                    
                    Presentacion.objects.create(
                        usuario=request.user,
                        nombre=copied_data['name'],
                        drive_id=copied_data['id'],
                        enlace_drive=copied_data['webView'],
                        miniatura_url=thumbnail_url
                    )
                    imported_count += 1
                    
            except HttpError as e:
                if e.resp.status == 404:
                    msg = f"La presentación con ID {presentation_id} no se encontró o no tienes permisos para copiarla."
                else:
                    msg = f"Ocurrió un error al importar la presentación {presentation_id}."
                errores.append(msg)
                logger.error(msg)
                continue

            except Exception as e:
                msg = f"Error inesperado al importar presentación {presentation_id}: {e}"
                errores.append(msg)
                logger.error(msg)
                continue
        
        if imported_count > 0:
            messages.success(request, f'Se importaron {imported_count} presentación(es) correctamente.')

        if errores:
            for err in errores:
                messages.error(request, err)

        if imported_count == 0 and not errores:
            messages.warning(request, 'No se pudo importar ninguna presentación.')

        if 'google_credentials' in request.session:
            del request.session['google_credentials']
        
        return redirect('home')
        
    except Exception as e:
        logger.error(f"Error al importar presentaciones: {e}")
        messages.error(request, f"Ocurrió un error al importar las presentaciones: {e}")
        return redirect('home')