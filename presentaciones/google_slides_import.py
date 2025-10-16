import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OAUTH2_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'oauth2.json')

SCOPES = [
    'https://www.googleapis.com/auth/presentations.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

def get_oauth_flow(redirect_uri):
    if not os.path.exists(OAUTH2_CREDENTIALS_FILE):
        raise FileNotFoundError(f"No se encuentra el archivo {OAUTH2_CREDENTIALS_FILE}")
    
    flow = Flow.from_client_secrets_file(
        OAUTH2_CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    return flow


def get_authorization_url(redirect_uri):
    flow = get_oauth_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return authorization_url, state


def get_credentials_from_code(code, state, redirect_uri):
    flow = get_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


def get_user_presentations(credentials_dict):
    credentials = Credentials(
        token=credentials_dict['token'],
        refresh_token=credentials_dict.get('refresh_token'),
        token_uri=credentials_dict['token_uri'],
        client_id=credentials_dict['client_id'],
        client_secret=credentials_dict['client_secret'],
        scopes=credentials_dict['scopes']
    )
    
    drive_service = build('drive', 'v3', credentials=credentials)
    
    results = drive_service.files().list(
        q="mimeType='application/vnd.google-apps.presentation' and trashed=false",
        pageSize=100,
        fields="files(id, name, webViewLink, thumbnailLink, createdTime, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    
    presentations = results.get('files', [])
    
    return presentations


def copy_presentation_to_drive(presentation_id, destination_folder_id, credentials_dict):
    credentials = Credentials(
        token=credentials_dict['token'],
        refresh_token=credentials_dict.get('refresh_token'),
        token_uri=credentials_dict['token_uri'],
        client_id=credentials_dict['client_id'],
        client_secret=credentials_dict['client_secret'],
        scopes=credentials_dict['scopes']
    )
    
    drive_service = build('drive', 'v3', credentials=credentials)
    
    copied_file = drive_service.files().copy(
        fileId=presentation_id,
        body={'parents': [destination_folder_id]}
    ).execute()
    
    return {
        'id': copied_file['id'],
        'name': copied_file['name'],
        'webView': f"https://docs.google.com/presentation/d/{copied_file['id']}/edit"
    }