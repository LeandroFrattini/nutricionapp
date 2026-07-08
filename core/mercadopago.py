"""
Integracion con Mercado Pago via OAuth (modelo marketplace).

Cada nutricionista vincula SU propia cuenta de Mercado Pago desde el
dashboard. NutricionClick nunca ve sus credenciales: solo guarda los
tokens que MP devuelve al autorizar. Los pagos de las señas van
directo a la cuenta del nutricionista.

Setup (una sola vez, del lado de NutricionClick):
  1. Crear una aplicacion en https://www.mercadopago.com.ar/developers/panel/app
     - Tipo de solucion: Pagos online -> CheckoutPro
     - Marcar "Plataforma o marketplace" si se quiere cobrar comision
  2. En "Editar aplicacion" configurar la Redirect URI:
       https://TU-DOMINIO/turnero/mp/callback/
  3. Copiar App ID y Client Secret al .env:
       MP_APP_ID=...
       MP_CLIENT_SECRET=...
       SITE_URL=https://TU-DOMINIO
"""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

MP_AUTH_URL = 'https://auth.mercadopago.com.ar/authorization'
MP_TOKEN_URL = 'https://api.mercadopago.com/oauth/token'
MP_PREFERENCES_URL = 'https://api.mercadopago.com/checkout/preferences'
MP_PAYMENTS_URL = 'https://api.mercadopago.com/v1/payments'


def _redirect_uri():
    return settings.SITE_URL.rstrip('/') + reverse('mp_callback')


def url_autorizacion(nutricionista):
    """URL a la que se envia al nutricionista para vincular su cuenta MP."""
    return (
        f'{MP_AUTH_URL}?client_id={settings.MP_APP_ID}'
        f'&response_type=code&platform_id=mp'
        f'&state={nutricionista.pk}'
        f'&redirect_uri={_redirect_uri()}'
    )


def intercambiar_codigo(code):
    """Cambia el authorization code por tokens. Devuelve dict o None."""
    try:
        resp = requests.post(MP_TOKEN_URL, json={
            'client_id': settings.MP_APP_ID,
            'client_secret': settings.MP_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': _redirect_uri(),
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error('MP intercambiar_codigo fallo: %s', exc)
        return None


def refrescar_token(turnero):
    """Refresca el access token si esta vencido. Devuelve True si quedo usable."""
    if not turnero.mp_refresh_token:
        return bool(turnero.mp_access_token)
    if turnero.mp_token_expira_en and turnero.mp_token_expira_en > timezone.now() + timedelta(minutes=10):
        return True
    try:
        resp = requests.post(MP_TOKEN_URL, json={
            'client_id': settings.MP_APP_ID,
            'client_secret': settings.MP_CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': turnero.mp_refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        guardar_tokens(turnero, data)
        return True
    except requests.RequestException as exc:
        logger.error('MP refrescar_token fallo para turnero %s: %s', turnero.pk, exc)
        return False


def guardar_tokens(turnero, data):
    turnero.mp_access_token = data.get('access_token', '')
    turnero.mp_refresh_token = data.get('refresh_token', '')
    turnero.mp_public_key = data.get('public_key', '')
    turnero.mp_user_id = str(data.get('user_id', ''))
    expires_in = data.get('expires_in')  # segundos
    if expires_in:
        turnero.mp_token_expira_en = timezone.now() + timedelta(seconds=int(expires_in))
    turnero.mp_conectado_en = timezone.now()
    turnero.save()


def desconectar(turnero):
    turnero.mp_access_token = ''
    turnero.mp_refresh_token = ''
    turnero.mp_public_key = ''
    turnero.mp_user_id = ''
    turnero.mp_token_expira_en = None
    turnero.mp_conectado_en = None
    turnero.save()


def crear_preferencia_sena(turno, turnero):
    """
    Crea una preferencia de CheckoutPro por la seña del turno,
    cobrando en la cuenta MP del nutricionista.
    Devuelve la URL de pago (init_point) o None.
    """
    if not refrescar_token(turnero):
        return None

    site = settings.SITE_URL.rstrip('/')
    nombre_nutri = turnero.nutricionista.user.get_full_name() or 'tu nutricionista'
    body = {
        'items': [{
            'title': f'Seña de turno con {nombre_nutri} — '
                     f'{turno.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")} hs',
            'quantity': 1,
            'currency_id': 'ARS',
            'unit_price': float(turno.sena_monto),
        }],
        'external_reference': str(turno.token),
        'back_urls': {
            'success': f'{site}/turnero/pago/{turno.token}/retorno/',
            'pending': f'{site}/turnero/pago/{turno.token}/retorno/',
            'failure': f'{site}/turnero/pago/{turno.token}/retorno/',
        },
        'auto_return': 'approved',
        'notification_url': f'{site}/turnero/mp/webhook/',
        'statement_descriptor': 'NUTRICIONCLICK',
    }
    if turno.email_destino:
        body['payer'] = {'email': turno.email_destino}
    # Comision opcional de la plataforma (0 por defecto)
    fee = getattr(settings, 'MP_MARKETPLACE_FEE', 0)
    if fee:
        body['marketplace_fee'] = float(fee)

    try:
        resp = requests.post(
            MP_PREFERENCES_URL, json=body,
            headers={'Authorization': f'Bearer {turnero.mp_access_token}'},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        turno.mp_preference_id = data.get('id', '')
        turno.save(update_fields=['mp_preference_id'])
        return data.get('init_point')
    except requests.RequestException as exc:
        logger.error('MP crear_preferencia fallo para turno %s: %s', turno.pk, exc)
        return None


def consultar_pago(payment_id, access_token):
    """Consulta un pago en la API de MP. Devuelve dict o None."""
    try:
        resp = requests.get(
            f'{MP_PAYMENTS_URL}/{payment_id}',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error('MP consultar_pago %s fallo: %s', payment_id, exc)
        return None


def verificar_pago_turno(turno, turnero):
    """
    Busca pagos aprobados asociados a la preferencia del turno.
    Se usa en el retorno del checkout y en el webhook.
    Devuelve el payment_id aprobado o None.
    """
    if not turno.mp_preference_id or not refrescar_token(turnero):
        return None
    try:
        resp = requests.get(
            'https://api.mercadopago.com/v1/payments/search',
            params={'external_reference': str(turno.token), 'sort': 'date_created', 'criteria': 'desc'},
            headers={'Authorization': f'Bearer {turnero.mp_access_token}'},
            timeout=15,
        )
        resp.raise_for_status()
        for pago in resp.json().get('results', []):
            if pago.get('status') == 'approved':
                return str(pago.get('id'))
        return None
    except requests.RequestException as exc:
        logger.error('MP verificar_pago_turno %s fallo: %s', turno.pk, exc)
        return None
