"""
Cobro de la suscripción a la PLATAFORMA (lo que cada nutricionista te paga a
vos por usar NutricionClick) — separado de core/mercadopago.py, que es la
integración OAuth para que cada nutricionista cobre SUS PROPIAS señas de
turnos con SU propia cuenta.

Acá se usa el access token de TU cuenta de Mercado Pago
(MP_ACCESS_TOKEN_PLATAFORMA), no el de cada nutricionista.

Modelo de cobro: todo pago (alta o renovación) es un cobro ÚNICO de Checkout
Pro por la cantidad de meses que el profesional elige pagar de una vez (1, 3,
6 o 12), con un % de descuento por volumen. No hay suscripción recurrente
automática de Mercado Pago — el profesional paga manualmente cada vez que
quiere renovar, y vos ves en tu panel quién está vencido.

Setup (una sola vez):
  1. Entrá a https://www.mercadopago.com.ar/developers/panel/app con TU cuenta
     (la que va a recibir el dinero de las suscripciones).
  2. Sección "Credenciales de producción" → copiá el "Access Token".
  3. Pegalo en el .env como MP_ACCESS_TOKEN_PLATAFORMA=...
  4. Mientras probás, usá las "Credenciales de prueba" (sandbox) de esa misma
     sección en vez de las de producción, para no mover plata real.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MP_PREFERENCES_URL = 'https://api.mercadopago.com/checkout/preferences'
MP_PAYMENTS_SEARCH_URL = 'https://api.mercadopago.com/v1/payments/search'

# % de descuento por volumen al pagar varios meses de una — el de 12 se
# maneja aparte más abajo (se paga 11, queda 1 mes gratis).
DESCUENTOS_VOLUMEN = {1: 0, 3: 5, 6: 8}
MESES_DISPONIBLES = [1, 3, 6, 12]


def _access_token():
    return getattr(settings, 'MP_ACCESS_TOKEN_PLATAFORMA', '') or ''


def configurado():
    """True si ya cargaste el access token de tu cuenta. Si no, no se puede
    cobrar nada por API todavía — hay que avisar en vez de romper."""
    return bool(_access_token())


def precio_mensual(tipo):
    """Precio de lista actual — mantené esto sincronizado con
    templates/emails/planes_info.html y templates/registration/registro.html
    si cambian los precios."""
    return {'base': 15000, 'premium': 40000}.get(tipo, 0)


def monto_por_meses(tipo, meses, codigo_descuento=None):
    """Precio total a cobrar por pagar `meses` meses de una sola vez.

    Si se pasa un código de descuento, se aplica SOLO sobre el pago de 1 mes
    (uso exclusivo del primer pago del registro) — nunca se combina con el
    descuento por volumen de pagar varios meses juntos."""
    precio_mes = precio_mensual(tipo)
    if codigo_descuento and meses == 1:
        return round(precio_mes * (1 - codigo_descuento.porcentaje_descuento / 100), 2)
    if meses == 12:
        return round(precio_mes * 11, 2)  # paga 11, se lleva 1 mes gratis
    descuento = DESCUENTOS_VOLUMEN.get(meses, 0)
    return round(precio_mes * meses * (1 - descuento / 100), 2)


def crear_pago(pago, titulo):
    """Crea una preferencia de Checkout Pro por el monto de `pago` (un
    PagoSuscripcion), como pago único. Devuelve la URL de pago (init_point) o
    None si falla o si todavía no está configurado el access token."""
    token = _access_token()
    if not token:
        logger.error('MP_ACCESS_TOKEN_PLATAFORMA no configurado — no se puede cobrar todavía.')
        return None
    nutri = pago.nutricionista
    site = settings.SITE_URL.rstrip('/')
    body = {
        'items': [{
            'title': titulo,
            'quantity': 1,
            'currency_id': 'ARS',
            'unit_price': float(pago.monto),
        }],
        'external_reference': f'pago-{pago.pk}',
        'back_urls': {
            'success': f'{site}/suscripcion/pago/{pago.pk}/retorno/',
            'pending': f'{site}/suscripcion/pago/{pago.pk}/retorno/',
            'failure': f'{site}/suscripcion/pago/{pago.pk}/retorno/',
        },
        'notification_url': f'{site}/suscripcion/mp/webhook/?pago={pago.pk}',
        'statement_descriptor': 'NUTRICIONCLICK',
        'payer': {'email': nutri.user.email},
    }
    # auto_return (te trae de vuelta solo, sin que cliquees "volver al sitio")
    # solo funciona con una URL pública real (https) — con localhost, Mercado
    # Pago rechaza toda la preferencia con un 400. En local lo omitimos.
    if site.startswith('https://'):
        body['auto_return'] = 'approved'
    try:
        resp = requests.post(
            MP_PREFERENCES_URL, json=body,
            headers={'Authorization': f'Bearer {token}'}, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        pago.mp_preference_id = data.get('id', '')
        pago.save(update_fields=['mp_preference_id'])
        return data.get('init_point')
    except requests.RequestException as exc:
        logger.error('MP crear_pago falló para pago %s: %s', pago.pk, exc)
        return None


def pago_fue_aprobado(pago):
    """Busca si ya hay un pago aprobado en MP asociado a esta preferencia.
    Se usa tanto en el retorno del checkout como en el webhook."""
    token = _access_token()
    if not token or not pago.mp_preference_id:
        return False
    try:
        resp = requests.get(
            MP_PAYMENTS_SEARCH_URL,
            params={'external_reference': f'pago-{pago.pk}', 'sort': 'date_created', 'criteria': 'desc'},
            headers={'Authorization': f'Bearer {token}'}, timeout=15,
        )
        resp.raise_for_status()
        for p in resp.json().get('results', []):
            if p.get('status') == 'approved':
                return True
        return False
    except requests.RequestException as exc:
        logger.error('MP pago_fue_aprobado falló para pago %s: %s', pago.pk, exc)
        return False
