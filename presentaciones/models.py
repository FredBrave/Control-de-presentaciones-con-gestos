from django.contrib.auth.models import AbstractUser
from django.db import models
import os
from django.conf import settings
from pdf2image import convert_from_path
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from googleapiclient.http import MediaIoBaseDownload
from .google_drive_oauth import get_drive_service
from tempfile import NamedTemporaryFile
from googleapiclient.discovery import build
import tempfile


class Usuario(AbstractUser):
    api_key = models.CharField(max_length=255, blank=True, null=True)

    def _str_(self):
        return self.username
    

class Presentacion(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='presentaciones'
    )
    nombre = models.CharField(max_length=255)
    drive_id = models.CharField(max_length=255)
    enlace_drive = models.URLField()
    miniatura = models.ImageField(upload_to='miniaturas/', blank=True, null=True)
    miniatura_url = models.URLField(blank=True, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_subida']

    def _str_(self):
        return f"{self.nombre} ({self.usuario})"

    def generar_miniatura(self):
        if self.miniatura_url:
            return
        
        try:
            service = get_drive_service()

            request = service.files().get_media(fileId=self.drive_id)
            pdf_path = os.path.join(tempfile.gettempdir(), f"temp_{self.id}.pdf")

            with open(pdf_path, 'wb') as f:
                downloader = service._http.request(request.uri)[1]
                f.write(downloader)

            poppler_path = os.path.join(settings.BASE_DIR, 'requeridos', 'poppler', 'Library', 'bin')
            poppler_path = os.path.abspath(poppler_path)

            pages = convert_from_path(pdf_path, first_page=1, last_page=1, poppler_path=poppler_path)
            if pages:
                thumb_io = BytesIO()
                
                target_width = 220
                target_height = 124
                
                img = pages[0]
                
                img_ratio = img.width / img.height
                target_ratio = target_width / target_height
                
                if img_ratio > target_ratio:
                    new_height = target_height
                    new_width = int(new_height * img_ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    left = (new_width - target_width) // 2
                    img = img.crop((left, 0, left + target_width, target_height))
                else:
                    new_width = target_width
                    new_height = int(new_width / img_ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    top = (new_height - target_height) // 2
                    img = img.crop((0, top, target_width, top + target_height))
                
                img.save(thumb_io, format='JPEG', quality=85, optimize=True)

                self.miniatura.save(
                    f"thumb_{self.id}.jpg",
                    ContentFile(thumb_io.getvalue()),
                    save=False
                )

            os.remove(pdf_path)

        except Exception as e:
            print(f"Error generando miniatura: {e}")