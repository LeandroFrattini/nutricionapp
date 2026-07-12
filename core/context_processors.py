from django.conf import settings


def datos_contacto(request):
    """Disponibiliza el WhatsApp y mail del negocio en TODOS los templates,
    para no tener que pasarlos a mano desde cada vista."""
    return {
        'ADMIN_WHATSAPP': settings.ADMIN_WHATSAPP,
        'ADMIN_EMAIL': settings.ADMIN_EMAIL,
        'ADMIN_URL': settings.ADMIN_URL,
    }


def nutri_actual(request):
    """Disponibiliza el perfil de Nutricionista del usuario logueado en TODOS
    los templates como `nutri` — de respaldo. base_dashboard.html decide qué
    mostrar en el sidebar (herramientas premium vs. cartel de "solo
    publicidad") en base a esta variable; si una vista se olvida de pasar
    `nutri` en su propio contexto (como pasaba en agenda/pacientes/etc.), el
    sidebar quedaba mostrando el cartel equivocado para CUALQUIER plan. Si la
    vista sí pasa su propio `nutri` explícito, ese gana — esto es solo el
    fallback para que nunca quede sin definir."""
    if not request.user.is_authenticated:
        return {}
    nutri = getattr(request.user, 'nutricionista', None)
    return {'nutri': nutri} if nutri else {}
