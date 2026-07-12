import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG es False por default a propósito: si alguien se olvida de configurar
# la variable de entorno en el servidor, el sitio arranca en modo seguro
# (sin tracebacks con código/settings expuestos a cualquier visitante) en vez
# de quedar abierto por accidente. Para desarrollo local, poné DEBUG=True
# en tu .env.
DEBUG = os.getenv("DEBUG", "False") == "True"

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # Solo para levantar el server en tu máquina sin configurar nada.
        SECRET_KEY = "django-insecure-solo-para-desarrollo-local"
    else:
        raise ImproperlyConfigured(
            "Falta SECRET_KEY en el entorno. Con DEBUG=False (producción) no se "
            "usa ninguna clave por default: generá una (podés usar "
            "`python -c \"from django.core.management.utils import get_random_secret_key; "
            "print(get_random_secret_key())\"`) y ponela en tu .env del servidor."
        )

# Dominios que puede servir el sitio. En local alcanza con localhost; en el
# servidor real hay que poner tu dominio en la variable de entorno
# ALLOWED_HOSTS (separados por coma), si no Django rechaza todos los pedidos.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# ── Endurecido de producción ─────────────────────────────────────────────
# Todo esto solo se activa con DEBUG=False, para no romper el desarrollo
# local (que corre por http:// sin certificado). Es el mismo set de flags
# que recomienda `manage.py check --deploy`.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Si el sitio corre detrás de un proxy/balanceador (nginx, Render, etc.)
    # que termina el HTTPS, esto le dice a Django que confíe en el header
    # que le manda el proxy en vez de rechazar la conexión como insegura.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

X_FRAME_OPTIONS = "DENY"

# ── URL del panel de administración ──────────────────────────────────────
# Por default Django lo sirve en /admin/, que es lo primero que prueban los
# bots y scanners automáticos. Esto no reemplaza la seguridad real (usuario +
# contraseña + django-axes ya lo protegen contra fuerza bruta), pero mover la
# URL a algo no adivinable corta casi todo ese tráfico de ruido. Se puede
# rotar en cualquier momento cambiando ADMIN_URL en el .env, sin tocar código.
ADMIN_URL = os.getenv("ADMIN_URL", "panel-2189425e/")
if not ADMIN_URL.endswith("/"):
    ADMIN_URL += "/"

# Si el sitio se sirve desde un dominio propio, agregalo acá (separados por
# coma) para que los formularios funcionen — si no, Django rechaza los POST.
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Cierra la sesión sola después de un tiempo de inactividad — con historias
# clínicas de por medio, no queremos sesiones abiertas eternamente en una
# compu compartida. 8 horas alcanza para un día de consultorio.
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_SAVE_EVERY_REQUEST = True  # cada request activo extiende la sesión

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "axes",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los archivos estáticos (CSS/JS/logos) directo desde el proceso de
    # Django, comprimidos y con cache-busting automático — sin esto, en
    # Render no habría quién sirva /static/ en producción (no hay nginx
    # aparte, es un solo proceso). Va justo después de SecurityMiddleware,
    # como pide la documentación de WhiteNoise.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "axes.middleware.AxesMiddleware",  # tiene que ir último
]

# django-authentication-backends: axes tiene que ir primero para poder
# bloquear el intento ANTES de que ModelBackend valide la contraseña.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ── Protección contra fuerza bruta en el login (django-axes) ─────────────
# Bloquea la combinación usuario+IP por un rato después de varios intentos
# fallidos seguidos, para que no se pueda probar contraseñas al infinito.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # horas hasta que se desbloquea solo
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]  # bloquea la COMBINACION, no cada uno por separado
AXES_RESET_ON_SUCCESS = True  # un login bien hecho borra los intentos fallidos previos
AXES_VERBOSE = False
AXES_LOCKOUT_TEMPLATE = "registration/bloqueado.html"

ROOT_URLCONF = "nutricion.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context_processors.datos_contacto",
        "core.context_processors.nutri_actual",
    ]},
}]

WSGI_APPLICATION = "nutricion.wsgi.application"

# En Render (u otro hosting con Postgres), la variable DATABASE_URL viene
# armada sola cuando conectás la base al servicio — no hay que tocar nada acá.
# En tu compu, como no está esa variable, sigue usando el mismo SQLite de
# siempre, sin ningún cambio en tu flujo local.
import dj_database_url

_database_url = os.getenv("DATABASE_URL", "")
if _database_url:
    DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path.home() / ".nutrilink" / "db.sqlite3",
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True
# Muestra los números grandes con puntos de miles (ej. $200.000) en vez de
# "$200000" — estándar argentino. Los montos que van directo a JavaScript
# (gráficos) están protegidos aparte con {% localize off %}, así que esto no
# les afecta.
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Almacenamiento de archivos subidos (fotos, PDFs) ─────────────────────
# En Render el disco es efímero: cualquier archivo que un nutricionista suba
# se perdería en el próximo deploy si se guardara ahí. Por eso, cuando estén
# configuradas las credenciales de Supabase Storage (compatible con S3), los
# archivos van directo ahí en vez de al disco local. Sin esas variables (como
# en tu compu), sigue guardando en la carpeta media/ de siempre.
#
# Van en DOS buckets separados, no uno solo:
#   - "publico": fotos de perfil de nutricionistas — se muestran sin login
#     en el directorio, así que no hay problema en que sean accesibles
#     directo por URL.
#   - "privado": PDFs de laboratorios/planes y archivos de pacientes —
#     información clínica. Este bucket NUNCA se expone por URL directa; los
#     archivos siguen sirviéndose solo a través de las vistas autenticadas
#     de siempre (core/views.py: laboratorio_descargar, plan_descargar,
#     archivo_ver), que ya validan que quien pide el archivo sea el
#     nutricionista dueño del paciente antes de mostrar nada. Storage es
#     transparente ahí: Django sigue leyendo el archivo igual, solo que
#     ahora los bytes vienen de Supabase en vez del disco.
SUPABASE_STORAGE_BUCKET_PUBLIC = os.getenv("SUPABASE_STORAGE_BUCKET_PUBLIC", "")
SUPABASE_STORAGE_BUCKET_PRIVATE = os.getenv("SUPABASE_STORAGE_BUCKET_PRIVATE", "")
SUPABASE_S3_ENDPOINT_URL = os.getenv("SUPABASE_S3_ENDPOINT_URL", "")
SUPABASE_S3_ACCESS_KEY_ID = os.getenv("SUPABASE_S3_ACCESS_KEY_ID", "")
SUPABASE_S3_SECRET_ACCESS_KEY = os.getenv("SUPABASE_S3_SECRET_ACCESS_KEY", "")
SUPABASE_S3_REGION = os.getenv("SUPABASE_S3_REGION", "us-east-1")

if SUPABASE_STORAGE_BUCKET_PUBLIC and SUPABASE_S3_ENDPOINT_URL:
    AWS_ACCESS_KEY_ID = SUPABASE_S3_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = SUPABASE_S3_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = SUPABASE_STORAGE_BUCKET_PUBLIC
    AWS_S3_ENDPOINT_URL = SUPABASE_S3_ENDPOINT_URL
    AWS_S3_REGION_NAME = SUPABASE_S3_REGION
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False  # URLs públicas simples, sin firma que vence
    AWS_S3_FILE_OVERWRITE = False
    _default_storage_backend = "storages.backends.s3boto3.S3Boto3Storage"
else:
    _default_storage_backend = "django.core.files.storage.FileSystemStorage"

STORAGES = {
    "default": {"BACKEND": _default_storage_backend},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_FROM = os.getenv("EMAIL_FROM", "NutricionClick <noreply@nutricionclick.com>")
DEFAULT_FROM_EMAIL = EMAIL_FROM
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "somosnutricionclick@gmail.com")
ADMIN_WHATSAPP = os.getenv("ADMIN_WHATSAPP", "")  # solo dígitos con código de país, ej: 5492914123456

_smtp_password = os.getenv("EMAIL_HOST_PASSWORD", "")
if _smtp_password:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", ADMIN_EMAIL)
    EMAIL_HOST_PASSWORD = _smtp_password
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Turnero online / Mercado Pago ────────────────────────────────────────
# URL publica del sitio (sin barra final). Se usa para armar los links de
# pago y el callback de OAuth de Mercado Pago.
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# Credenciales de la APLICACION de NutricionClick en Mercado Pago
# (panel de desarrolladores: https://www.mercadopago.com.ar/developers/panel/app)
# Cada nutricionista vincula su propia cuenta via OAuth; estos datos son
# solo de la app de la plataforma.
MP_APP_ID = os.getenv("MP_APP_ID", "")
MP_CLIENT_SECRET = os.getenv("MP_CLIENT_SECRET", "")

# Comision fija de la plataforma por seña cobrada (en ARS). 0 = sin comision.
MP_MARKETPLACE_FEE = float(os.getenv("MP_MARKETPLACE_FEE", "0"))

# Access Token de TU cuenta de Mercado Pago (no la app OAuth de arriba) —
# se usa para cobrar la suscripción de la plataforma cuando hay código de
# descuento (pago único del primer mes + suscripción recurrente). Se saca de
# mercadopago.com.ar/developers/panel/app → Credenciales de producción.
# Mientras probás, usá las Credenciales de prueba (sandbox) en su lugar.
MP_ACCESS_TOKEN_PLATAFORMA = os.getenv("MP_ACCESS_TOKEN_PLATAFORMA", "")

# Clave secreta del webhook de suscripciones — para verificar que la
# notificación realmente vino de Mercado Pago (firma HMAC), no de un tercero
# imitando la URL. Se saca del mismo panel donde se configura el webhook.
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
