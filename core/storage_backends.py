"""
Storage dedicado para los archivos clínicos (PDFs de laboratorios/planes,
archivos de pacientes) — separado del storage "default" (que es el bucket
público de fotos de nutricionistas, configurado en settings.py).

Este bucket es privado: nunca se genera ni se expone una URL directa de estos
archivos. Siempre se sirven a través de las vistas autenticadas de
core/views.py (laboratorio_descargar, plan_descargar, archivo_ver), que
validan el dueño antes de leer el archivo — Storage es un detalle interno,
transparente para esas vistas.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


class SupabasePrivateStorage(S3Boto3Storage):
    bucket_name = settings.SUPABASE_STORAGE_BUCKET_PRIVATE
    endpoint_url = settings.SUPABASE_S3_ENDPOINT_URL
    access_key = settings.SUPABASE_S3_ACCESS_KEY_ID
    secret_key = settings.SUPABASE_S3_SECRET_ACCESS_KEY
    region_name = settings.SUPABASE_S3_REGION
    addressing_style = "path"
    default_acl = None
    querystring_auth = True
    file_overwrite = False


def storage_archivos_clinicos():
    """Se pasa como callable (no instancia) al `storage=` de los FileField,
    para que Django elija el backend correcto en cada entorno recién al
    guardar/leer un archivo — no al definir el modelo. Sin las credenciales
    de Supabase configuradas (como en desarrollo local), cae al disco local
    de siempre, sin romper nada."""
    if settings.SUPABASE_STORAGE_BUCKET_PRIVATE and settings.SUPABASE_S3_ENDPOINT_URL:
        return SupabasePrivateStorage()
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
