import os
import pickle
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'oauth.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'config', 'token.pickle')


def get_drive_service():
    """Obtiene el servicio de Drive autenticado con OAuth."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.info("Abriendo navegador para autenticación OAuth con Google Drive...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service


def get_or_create_user_folder(user):
    service = get_drive_service()

    PARENT_FOLDER_ID = '1E4I8mIp6PAUaJdXIax9rplVBmdS3sbGR'

    user_folder_name = user.username
    try:
        query = f"name = '{user_folder_name}' and '{PARENT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        response = service.files().list(q=query, fields='files(id, name)').execute()
        files = response.get('files', [])

        if files:
            folder_id = files[0]['id']
            logger.info(f"Carpeta existente encontrada para {user_folder_name}: {folder_id}")
            return folder_id
        else:
            metadata = {
                'name': user_folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [PARENT_FOLDER_ID],
            }
            folder = service.files().create(body=metadata, fields='id').execute()
            folder_id = folder['id']
            logger.info(f"Carpeta creada para {user_folder_name}: {folder_id}")
            return folder_id
    except Exception as e:
        logger.error(f"Error al obtener/crear carpeta de Drive para {user.username}: {e}")
        return None


def upload_to_drive(filepath, filename, folder_id):
    service = get_drive_service()

    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(filepath, resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, thumbnailLink, webViewLink'
    ).execute()

    service.permissions().create(
        fileId=uploaded.get('id'),
        body={'role': 'reader', 'type': 'anyone'},
    ).execute()

    return {
        'id': uploaded.get('id'),
        'name': uploaded.get('name'),
        'thumbnail': uploaded.get('thumbnailLink'),
        'webView': uploaded.get('webViewLink')
    }