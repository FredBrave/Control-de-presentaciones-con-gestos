from django.shortcuts import render, redirect, get_object_or_404
import os, cv2
import traceback
import logging
from django.core.files import File
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .forms import CustomUserCreationForm
from django.contrib.auth import get_user_model
from google.oauth2 import service_account
from .google_drive_oauth import get_or_create_user_folder, upload_to_drive
from googleapiclient.discovery import build
import tempfile
from django.http import JsonResponse
from django.urls import reverse
from CPG import settings
import time, subprocess, threading
from .models import Presentacion
from django.contrib.auth.decorators import login_required
from .forms import UploadPresentationForm
from .google_slides_import import (
    get_authorization_url, 
    get_credentials_from_code,
    get_user_presentations,
    copy_presentation_to_drive
)
from django.views.decorators.csrf import csrf_exempt
import json

# Variables Globales
logger = logging.getLogger(__name__)
detector_process = None
detector_thread = None
detector_running = False
User = get_user_model()
ultimo_comando = None
def safe_remove(path, retries=3, delay=1):
    for i in range(retries):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            time.sleep(delay)


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
                return redirect('presentaciones:home')
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
            return redirect("presentaciones:home")  
        else:
            messages.error(request, "Usuario o contraseña incorrectos")

    return render(request, "seguridad/login.html")

@login_required
def logoutUser(request):
    logout(request)
    return redirect('presentaciones:login')

@login_required
def home(request):
    presentaciones = Presentacion.objects.filter(usuario=request.user).order_by('-fecha_subida')[:10]

    context = {
        'presentaciones': presentaciones
    }
    return render(request, 'presentaciones/home.html', context)

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

                        return redirect('presentaciones:upload')
                    
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

                if not upload_name.lower().endswith('.pdf'):
                    messages.error(request, 'Solo se permiten archivos PDF o PPTX.')
                    return redirect('presentaciones:upload')

                if not upload_name.lower().endswith('.pdf'):
                    messages.error(request, 'Solo se permiten archivos PDF o PPTX.')
                    return redirect('presentaciones:upload')

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
                    
                    messages.success(request, f'Presentación "{titulo}" subida correctamente a Google Drive.')                
                else:
                    presentacion = Presentacion.objects.create(
                        usuario=user,
                        nombre=upload_name,
                        titulo=titulo,
                        ubicacion='local'
                    )
                    
                    with open(upload_path, 'rb') as f:
                        presentacion.archivo_local.save(upload_name, File(f), save=False)
                    
                    messages.success(request, f'Presentación "{titulo}" guardada correctamente en el servidor.')

                try:
                    presentacion.generar_miniatura()
                except Exception as e:
                    logger.warning(f"Error al generar miniatura: {e}")
                
                presentacion.save()

                return redirect('presentaciones:home')
            except Exception as e:
                error_traceback = traceback.format_exc()
                logger.error(f"Error durante la subida para {user.username}: {e}")
                logger.error(error_traceback)
                messages.error(request, f'Ocurrió un error al procesar tu archivo: {str(e)}')

                return redirect('presentaciones:upload')
            
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
    redirect_uri = request.build_absolute_uri(reverse('presentaciones:oauth2callback'))
    
    try:
        authorization_url, state = get_authorization_url(redirect_uri)
        request.session['oauth_state'] = state
        return redirect(authorization_url)
    except Exception as e:
        logger.error(f"Error al iniciar OAuth: {e}")
        messages.error(request, 'Error al conectar con Google. Verifica tu configuración.')
        return redirect('presentaciones:home')

@login_required
def oauth2callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'Error de autorización: {error}')

        return redirect('presentaciones:home')
    
    session_state = request.session.get('oauth_state')
    if not state or state != session_state:
        messages.error(request, 'Error de seguridad. Intenta nuevamente.')

        return redirect('presentaciones:home')
    
    try:
        redirect_uri = request.build_absolute_uri(reverse('presentaciones:oauth2callback'))
        credentials_dict = get_credentials_from_code(code, state, redirect_uri)
        
        request.session['google_credentials'] = credentials_dict
        

        return redirect('presentaciones:select_presentations')
        
    except Exception as e:
        logger.error(f"Error en OAuth callback: {e}")
        messages.error(request, 'Error al procesar la autorización.')

        return redirect('presentaciones:home')


@login_required
def select_presentations(request):
    credentials_dict = request.session.get('google_credentials')
    
    if not credentials_dict:
        messages.error(request, 'Sesión expirada. Por favor, autoriza nuevamente.')

        return redirect('presentaciones:import_from_google_slides')
    
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

        return redirect('presentaciones:home')


@login_required
def import_selected_presentations(request):
    if request.method != 'POST':

        return redirect('presentaciones:select_presentations')
    
    credentials_dict = request.session.get('google_credentials')
    
    if not credentials_dict:
        messages.error(request, 'Sesión expirada. Por favor, autoriza nuevamente.')

        return redirect('presentaciones:import_from_google_slides')
    
    selected_ids = request.POST.getlist('presentations')
    
    if not selected_ids:
        messages.warning(request, 'No seleccionaste ninguna presentación.')

        return redirect('presentaciones:select_presentations')
    
    try:
        folder_id = get_or_create_user_folder(request.user)
        
        if not folder_id:
            raise Exception("No se pudo obtener la carpeta del usuario.")
        
        imported_count = 0

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
                    

                    presentacion = Presentacion.objects.create(
                        usuario=request.user,
                        nombre=copied_data['name'],
                        drive_id=copied_data['id'],
                        enlace_drive=copied_data['webView'],
                        miniatura_url=thumbnail_url
                    )
                    imported_count += 1
            except Exception as e:
                logger.error(f"Error al importar presentación {presentation_id}: {e}")
                continue
        
        if imported_count > 0:
            messages.success(
                request, 
                f'Se importaron {imported_count} presentación(es) correctamente.'
            )
        else:
            messages.warning(request, 'No se pudo importar ninguna presentación.')
        
        if 'google_credentials' in request.session:
            del request.session['google_credentials']
        
        return redirect('presentaciones:home')
        
    except Exception as e:
        logger.error(f"Error al importar presentaciones: {e}")
        messages.error(request, 'Error al importar las presentaciones.')
        return redirect('presentaciones:home')
    

detector_process = None
detector_thread = None
detector_running = False


@login_required
def presentar(request, presentacion_id):
    presentacion = get_object_or_404(Presentacion, id=presentacion_id, usuario=request.user)
    
    tipo_almacenamiento = 'drive' if presentacion.enlace_drive else 'local'
    
    url_pdf = None
    tipo_archivo = None
    
    if tipo_almacenamiento == 'drive':
        url_pdf = presentacion.enlace_drive
        tipo_archivo = 'drive'
    else:
        if presentacion.archivo_local:
            extension = presentacion.archivo_local.name.split('.')[-1].lower()
            tipo_archivo = extension
            
            if extension == 'pdf':
                url_pdf = presentacion.archivo_local.url
            elif extension in ['pptx', 'ppt', 'odp']:
                url_pdf = f"https://docs.google.com/viewer?url={request.build_absolute_uri(presentacion.archivo_local.url)}&embedded=true"
    
    global detector_process, detector_running
    
    detector_iniciado = False
    mensaje_detector = ""
    
    if not detector_running:
        try:
            cap = cv2.VideoCapture(0)
            
            if cap.isOpened():
                cap.release()
                time.sleep(0.5)
                
                detector_process = subprocess.Popen(
                    ['python', 'manage.py', 'detectar_gestos'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                detector_running = True
                time.sleep(2)
                
                if detector_process.poll() is None:
                    detector_iniciado = True
                    mensaje_detector = "Detector de gestos iniciado correctamente"
                else:
                    detector_running = False
                    mensaje_detector = "Error: El detector no pudo iniciarse"
            else:
                cap.release()
                mensaje_detector = "Advertencia: No se detectó cámara"
                
        except ImportError:
            mensaje_detector = "Error: OpenCV no está instalado"
        except Exception as e:
            detector_running = False
            mensaje_detector = f"Error al iniciar detector: {str(e)}"
    else:
        detector_iniciado = True
        mensaje_detector = "Detector ya está en ejecución"
    
    context = {
        'presentacion': presentacion,
        'url_pdf': url_pdf,
        'tipo_almacenamiento': tipo_almacenamiento,
        'tipo_archivo': tipo_archivo,
        'debug': settings.DEBUG,
        'detector_iniciado': detector_iniciado,
        'mensaje_detector': mensaje_detector,
    }
    
    return render(request, 'presentaciones/presentar.html', context)


@login_required
def iniciar_detector(request):
    global detector_process, detector_thread, detector_running
    
    if detector_running:
        return JsonResponse({
            'success': True,
            'message': 'Detector ya está en ejecución',
            'status': 'running'
        })
    
    try:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            cap.release()
            return JsonResponse({
                'success': False,
                'message': 'No se pudo acceder a la cámara',
                'error': 'camera_not_found'
            })
        
        cap.release()
        time.sleep(0.5)
        
        detector_process = subprocess.Popen(
            ['python', 'manage.py', 'detectar_gestos'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        detector_running = True
        
        time.sleep(2)
        
        if detector_process.poll() is not None:
            detector_running = False
            return JsonResponse({
                'success': False,
                'message': 'Error al iniciar el detector',
                'error': 'detector_failed'
            })
        
        return JsonResponse({
            'success': True,
            'message': 'Detector iniciado correctamente',
            'status': 'started'
        })
        
    except ImportError:
        return JsonResponse({
            'success': False,
            'message': 'OpenCV no está instalado',
            'error': 'opencv_missing'
        })
    except Exception as e:
        detector_running = False
        return JsonResponse({
            'success': False,
            'message': f'Error al iniciar el detector: {str(e)}',
            'error': 'unknown_error'
        })


@login_required
def detener_detector(request):
    global detector_process, detector_running
    
    if not detector_running or detector_process is None:
        return JsonResponse({
            'success': True,
            'message': 'Detector no está en ejecución',
            'status': 'stopped'
        })
    
    try:
        detector_process.terminate()
        
        try:
            detector_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            detector_process.kill()
        
        detector_running = False
        detector_process = None
        
        return JsonResponse({
            'success': True,
            'message': 'Detector detenido correctamente',
            'status': 'stopped'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al detener el detector: {str(e)}',
            'error': 'stop_failed'
        })


@login_required
def verificar_estado_detector(request):
    global detector_process, detector_running
    
    if not detector_running or detector_process is None:
        return JsonResponse({
            'running': False,
            'status': 'stopped'
        })
    
    if detector_process.poll() is not None:
        detector_running = False
        detector_process = None
        return JsonResponse({
            'running': False,
            'status': 'crashed'
        })
    
    return JsonResponse({
        'running': True,
        'status': 'running'
    })


@csrf_exempt
def comando_gesto(request):
    global ultimo_comando
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comando = data.get('comando')
            
            if comando:
                ultimo_comando = comando
                print(f"[COMANDO] Recibido: {comando}")
                return JsonResponse({
                    'success': True,
                    'comando': comando,
                    'message': 'Comando actualizado'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'No se proporcionó comando'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'JSON inválido'
            }, status=400)
    
    elif request.method == 'GET':
        if ultimo_comando:
            comando_actual = ultimo_comando
            ultimo_comando = None
            return JsonResponse({
                'success': True,
                'comando': comando_actual
            })
        else:
            return JsonResponse({
                'success': True,
                'comando': None
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)
