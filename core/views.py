import uuid
from datetime import date, datetime, timedelta
from urllib.parse import quote
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from .models import Nutricionista, Paciente, Turno, Medicion, Laboratorio, PlanAlimentario, Consulta, ArchivoPaciente, Ciudad
from .utils import telefono_whatsapp_ar, nutri_requerido, nutri_requerido_cualquier_plan, sumar_un_mes
from .forms import (RegistroForm, PerfilForm, ContactoForm, PacienteForm, TurnoForm,
                    MedicionForm, LaboratorioForm, PlanAlimentarioForm, ConsultaForm, ArchivoPacienteForm)


# ─── PUBLICAS ─────────────────────────────────────────────────────────────────

def _visibles_publicamente():
    """Nutricionistas que se muestran en el directorio y la home: aprobados,
    con el usuario activo, no ocultos (cuentas internas/de prueba), y que no
    estén suspendidos por falta de pago hace más de 5 días (las cuentas
    exentas de pago nunca quedan afuera por esto)."""
    from django.db.models import Q
    limite = date.today() - timedelta(days=5)
    return Nutricionista.objects.filter(
        aprobado=True, user__is_active=True, oculto=False
    ).filter(
        Q(exento_de_pago=True) | Q(proxima_revision_pago__isnull=True) | Q(proxima_revision_pago__gte=limite)
    ).select_related('user', 'ciudad', 'ciudad__pais').prefetch_related('obras_sociales')


@never_cache
def home(request):
    base_qs = _visibles_publicamente()
    destacados = list(base_qs.filter(destacado=True).order_by('?')[:6])
    # Si no hay destacados (plan premium), mostrar 6 aprobados al azar
    if not destacados:
        destacados = list(base_qs.order_by('?')[:6])
    total_nutricionistas = base_qs.count()
    return render(request, 'home.html', {
        'destacados': destacados,
        'total_nutricionistas': total_nutricionistas,
    })


@never_cache
def nutricionistas_lista(request):
    from django.db.models import Q
    from .models import ObraSocial, Ciudad, Pais
    qs = _visibles_publicamente()
    q = request.GET.get('q', '').strip()
    especialidad = request.GET.get('especialidad', '')
    edad = request.GET.get('edad', '')
    composicion = request.GET.get('composicion', '')
    modalidad = request.GET.get('modalidad', '')
    obra_social = request.GET.get('obra_social', '')
    ciudad = request.GET.get('ciudad', '')
    pais = request.GET.get('pais', '')
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q)|Q(user__last_name__icontains=q)|Q(bio__icontains=q))
    if especialidad:
        qs = qs.filter(especialidades__icontains=especialidad)
    if edad:
        qs = qs.filter(edades_atendidas__icontains=edad)
    if composicion:
        qs = qs.filter(composicion_corporal__icontains=composicion)
    if modalidad:
        qs = qs.filter(modalidad=modalidad)
    if obra_social:
        qs = qs.filter(obras_sociales__id=obra_social)
    if pais:
        qs = qs.filter(ciudad__pais__id=pais)
    if ciudad:
        qs = qs.filter(ciudad__id=ciudad)
    total = qs.count()
    return render(request, 'nutricionistas/lista.html', {
        'nutricionistas': qs,
        'total': total,
        'q': q, 'especialidad': especialidad, 'edad': edad, 'composicion': composicion,
        'modalidad': modalidad, 'obra_social': obra_social, 'ciudad': ciudad, 'pais': pais,
        'especialidades': Nutricionista.ESPECIALIDADES,
        'edades': Nutricionista.EDADES,
        'composiciones': Nutricionista.COMPOSICION_CORPORAL,
        'modalidades': Nutricionista.MODALIDADES,
        'obras_sociales': ObraSocial.objects.filter(activa=True),
        'ciudades': Ciudad.objects.filter(activa=True),
        'paises': Pais.objects.filter(activo=True),
    })


@never_cache
def perfil_publico(request, slug):
    # "Ver como me ven": si el que mira es el propio nutricionista, le
    # mostramos su perfil SIEMPRE, aunque hoy no cumpla los requisitos para
    # aparecer publicamente (oculto, sin aprobar, suspendido por pago) — sino
    # el boton de su propio dashboard le tira un 404 sin explicacion, que
    # parece que "se rompio la web" en vez de avisarle por que no esta visible.
    propio = getattr(request.user, 'nutricionista', None) if request.user.is_authenticated else None
    if propio and propio.slug == slug:
        razon_no_visible = None
        if not _visibles_publicamente().filter(pk=propio.pk).exists():
            if not propio.aprobado:
                razon_no_visible = 'Tu cuenta todavía no fue aprobada.'
            elif propio.oculto:
                razon_no_visible = 'Tu perfil está marcado como "oculto" — no aparece en el directorio ni en las búsquedas.'
            elif propio.suspendido_por_pago():
                razon_no_visible = 'Tu cuenta está suspendida por falta de pago.'
            else:
                razon_no_visible = 'Tu perfil no está visible públicamente en este momento.'
        return render(request, 'perfil/publico.html', {
            'nutricionista': propio, 'es_vista_previa': True, 'razon_no_visible': razon_no_visible,
        })

    nutricionista = get_object_or_404(_visibles_publicamente(), slug=slug)
    return render(request, 'perfil/publico.html', {'nutricionista': nutricionista})


def que_puedo_hacer(request):
    """Recorrido de funciones para alguien evaluando sumarse — pensado para
    linkear desde 'Quiero ser parte' y desde los anuncios."""
    total_activos = _visibles_publicamente().count()
    return render(request, 'que_puedo_hacer.html', {'total_activos': total_activos})


def quiero_ser_parte(request):
    enviado = False
    plan_inicial = request.GET.get('plan', 'herramientas')
    if request.method == 'POST':
        form = ContactoForm(request.POST)
        if form.is_valid():
            from .models import ContactoInteresado
            from .emails import enviar_planes_info
            cd = form.cleaned_data
            contacto = ContactoInteresado.objects.create(
                email=cd['email'],
                telefono=cd.get('telefono', ''),
                plan_interes=cd['plan_interes'],
            )
            try:
                enviar_planes_info(contacto)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error enviando mail de planes al interesado: {e}")
            planes = {
                'herramientas': 'Plan Completo (Publicidad + Herramientas)',
                'publicidad': 'Plan Básico (Solo publicidad)',
                'sin_definir': 'Sin definir',
            }
            try:
                telefono_linea = f"WhatsApp: {cd['telefono']}\n" if cd.get('telefono') else ''
                send_mail(
                    subject=f"[NutricionClick] 🆕 Pidió información — {planes.get(cd['plan_interes'], '')}",
                    message=f"Email: {cd['email']}\n{telefono_linea}Plan: {planes.get(cd['plan_interes'], cd['plan_interes'])}\n",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],
                    fail_silently=False,
                )
            except Exception as e:
                # Si falla el mail, igual mostramos éxito al visitante pero lo logueamos
                import logging
                logging.getLogger(__name__).error(f"Error enviando mail de contacto: {e}")
            enviado = True
    else:
        form = ContactoForm(plan_inicial=plan_inicial)
    return render(request, 'quiero_ser_parte.html', {
        'form': form,
        'enviado': enviado,
        'plan_inicial': plan_inicial,
    })


def registro(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_mail(
                subject='[NutricionClick] Nueva solicitud de nutricionista',
                message=f'Nuevo registro: {user.get_full_name()} ({user.email}). Revisalo en el admin.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
            nutri = user.nutricionista
            return redirect('registro_pagar', pk=nutri.pk)
    else:
        # ?plan=publicidad|herramientas viene de los botones de la landing
        # (quiero_ser_parte.html) — se traduce a los choices reales de tipo.
        plan_map = {'publicidad': 'base', 'herramientas': 'premium'}
        plan_inicial = plan_map.get(request.GET.get('plan'), 'premium')
        form = RegistroForm(initial={'plan_suscripcion': plan_inicial})
    return render(request, 'registration/registro.html', {'form': form})


def en_revision(request):
    return render(request, 'en_revision.html')


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def _semana_lun_sab(fecha_ref):
    """Devuelve lista de 6 dates: Lunes a Sabado de la semana de fecha_ref."""
    inicio = fecha_ref - timedelta(days=fecha_ref.weekday())  # lunes
    return [inicio + timedelta(days=i) for i in range(6)]


@login_required
def dashboard(request):
    try:
        nutri = request.user.nutricionista
    except Nutricionista.DoesNotExist:
        return redirect('home')
    if not nutri.aprobado:
        return redirect('en_revision')
    if nutri.suspendido_por_pago():
        return redirect('perfil_suspendido')
    if nutri.tipo != 'premium':
        # Plan básico (solo publicidad): no tiene turnos/pacientes que
        # mostrar acá — lo mandamos directo a lo único que puede hacer,
        # editar su perfil público, en vez de rebotarlo a la home sin
        # ninguna explicación.
        return redirect('perfil_editar')

    hoy = date.today()
    dias_semana = _semana_lun_sab(hoy)

    turnos_hoy = Turno.objects.filter(
        nutricionista=nutri, fecha_hora_inicio__date=hoy,
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha_hora_inicio')

    # Conteo por dia para la vista semanal
    turnos_semana_qs = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__date__gte=dias_semana[0],
        fecha_hora_inicio__date__lte=dias_semana[-1],
        estado__in=['pendiente', 'confirmado'],
    )
    conteo_por_dia = {d: 0 for d in dias_semana}
    for t in turnos_semana_qs:
        d = timezone.localtime(t.fecha_hora_inicio).date()
        if d in conteo_por_dia:
            conteo_por_dia[d] += 1
    total_semana = sum(conteo_por_dia.values())

    proximos = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__gte=timezone.now(),
        estado__in=['pendiente', 'confirmado'],
    ).order_by('fecha_hora_inicio')[:5]

    total_pacientes = Paciente.objects.filter(nutricionista=nutri, activo=True).count()

    dias_venc = nutri.dias_para_vencimiento()
    mostrar_aviso_vencimiento = not nutri.exento_de_pago and dias_venc is not None and dias_venc <= 15

    return render(request, 'dashboard/dashboard.html', {
        'nutri': nutri, 'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'total_pacientes': total_pacientes,
        'total_semana': total_semana,
        'proximos': proximos,
        'dias_semana': dias_semana,
        'conteo_por_dia': conteo_por_dia,
        'dias_venc': dias_venc,
        'dias_vencido_abs': abs(dias_venc) if dias_venc is not None and dias_venc < 0 else None,
        'mostrar_aviso_vencimiento': mostrar_aviso_vencimiento,
    })


@login_required
@nutri_requerido_cualquier_plan
def perfil_editar(request, nutri):
    if request.method == 'POST':
        form = PerfilForm(request.POST, request.FILES, instance=nutri)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado.')
            return redirect('perfil_editar')
    else:
        form = PerfilForm(instance=nutri)
    return render(request, 'perfil/editar.html', {'form': form, 'nutri': nutri})


def ciudades_por_provincia(request):
    """Devuelve las <option> de ciudades de una provincia — para el
    desplegable en cascada de Provincia → Ciudad (htmx). No requiere login:
    no expone nada sensible, solo nombres de ciudades."""
    provincia_id = request.GET.get('provincia')
    ciudades = Ciudad.objects.filter(
        provincia_id=provincia_id, activa=True
    ).order_by('nombre') if provincia_id else Ciudad.objects.none()
    return render(request, 'partials/opciones_ciudad.html', {'ciudades': ciudades})


# ─── PACIENTES ────────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def pacientes_lista(request, nutri):
    q = request.GET.get('q', '').strip()
    activo_filter = request.GET.get('activo', '1')
    qs = Paciente.objects.filter(nutricionista=nutri)
    if activo_filter == '1':
        qs = qs.filter(activo=True)
    elif activo_filter == '0':
        qs = qs.filter(activo=False)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(email__icontains=q))
    return render(request, 'pacientes/lista.html', {'pacientes': qs.order_by('apellido', 'nombre'), 'q': q, 'activo_filter': activo_filter})


@login_required
@nutri_requerido
def paciente_nuevo(request, nutri):
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.nutricionista = nutri
            p.save()
            messages.success(request, f'Paciente {p.nombre_completo} agregado.')
            return redirect('paciente_detalle', pk=p.pk)
    else:
        # Si viene desde un turno de reserva online sin paciente vinculado
        # (agenda/recordatorios), precargamos con los datos de contacto que
        # la persona ya completó al reservar, para no hacer que el
        # nutricionista los vuelva a tipear.
        initial = {
            'nombre': request.GET.get('nombre', ''),
            'apellido': request.GET.get('apellido', ''),
            'telefono': request.GET.get('telefono', ''),
            'email': request.GET.get('email', ''),
        }
        form = PacienteForm(initial=initial)
    return render(request, 'pacientes/form.html', {'form': form, 'titulo': 'Nuevo paciente'})


@login_required
@nutri_requerido
def paciente_editar(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = PacienteForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paciente actualizado.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = PacienteForm(instance=paciente)
    return render(request, 'pacientes/form.html', {'form': form, 'paciente': paciente, 'titulo': f'Editar — {paciente.nombre_completo}'})


@login_required
@nutri_requerido
def paciente_detalle(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    tab = request.GET.get('tab', 'historia')
    mediciones = list(paciente.mediciones.all()[:20])
    mediciones_chart = list(reversed(mediciones))  # cronologico para el grafico
    laboratorios = paciente.laboratorios.all()[:10]
    planes = paciente.planes.all()[:10]
    consultas = paciente.consultas.all()[:10]
    archivos = list(paciente.archivos.all()[:20])
    if paciente.telefono:
        telefono_limpio = telefono_whatsapp_ar(paciente.telefono)
        for archivo in archivos:
            archivo_url = f"{settings.SITE_URL}{reverse('archivo_ver', args=[archivo.token])}"
            mensaje = f'Hola {paciente.nombre}, te envío tu archivo "{archivo.nombre}": {archivo_url}'
            archivo.whatsapp_url = f"https://wa.me/{telefono_limpio}?text={quote(mensaje)}"
    ultima_medicion = mediciones[0] if mediciones else None
    return render(request, 'pacientes/detalle.html', {
        'paciente': paciente, 'nutri': nutri, 'tab': tab,
        'mediciones': mediciones, 'mediciones_chart': mediciones_chart,
        'laboratorios': laboratorios, 'planes': planes, 'consultas': consultas,
        'archivos': archivos,
        'ultima_medicion': ultima_medicion,
    })


@login_required
@nutri_requerido
def paciente_archivar(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    paciente.activo = False
    paciente.save()
    messages.success(request, f'{paciente.nombre_completo} archivado.')
    return redirect('pacientes_lista')


@login_required
@nutri_requerido
def paciente_reactivar(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    paciente.activo = True
    paciente.save()
    messages.success(request, f'{paciente.nombre_completo} reactivado.')
    return redirect(f"{reverse('pacientes_lista')}?activo=1")


# ─── MEDICIONES ──────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def medicion_nueva(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = MedicionForm(request.POST)
        if form.is_valid():
            m = form.save(commit=False); m.paciente = paciente; m.save()
            messages.success(request, 'Medicion guardada.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = MedicionForm()
    return render(request, 'pacientes/medicion_form.html', {'form': form, 'paciente': paciente, 'titulo': 'Nueva medicion'})


@login_required
@nutri_requerido
def medicion_editar(request, nutri, pk, mid):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    medicion = get_object_or_404(Medicion, pk=mid, paciente=paciente)
    if request.method == 'POST':
        form = MedicionForm(request.POST, instance=medicion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Medicion actualizada.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = MedicionForm(instance=medicion)
    return render(request, 'pacientes/medicion_form.html', {'form': form, 'paciente': paciente, 'medicion': medicion, 'titulo': 'Editar medicion'})


# ─── LABORATORIO ─────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def laboratorio_nuevo(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = LaboratorioForm(request.POST, request.FILES)
        if form.is_valid():
            lab = form.save(commit=False); lab.paciente = paciente; lab.save()
            messages.success(request, 'Laboratorio guardado.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = LaboratorioForm()
    return render(request, 'pacientes/laboratorio_form.html', {'form': form, 'paciente': paciente, 'titulo': 'Nuevo laboratorio'})


@login_required
@nutri_requerido
def laboratorio_editar(request, nutri, pk, lid):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    lab = get_object_or_404(Laboratorio, pk=lid, paciente=paciente)
    if request.method == 'POST':
        form = LaboratorioForm(request.POST, request.FILES, instance=lab)
        if form.is_valid():
            form.save()
            messages.success(request, 'Laboratorio actualizado.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = LaboratorioForm(instance=lab)
    return render(request, 'pacientes/laboratorio_form.html', {'form': form, 'paciente': paciente, 'lab': lab, 'titulo': 'Editar laboratorio'})


@login_required
@nutri_requerido
def laboratorio_descargar(request, nutri, pk, lid):
    """Sirve el PDF de un laboratorio solo al nutricionista dueño del paciente."""
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    lab = get_object_or_404(Laboratorio, pk=lid, paciente=paciente)
    if not lab.archivo_pdf:
        raise Http404
    return FileResponse(lab.archivo_pdf.open('rb'), filename=lab.archivo_pdf.name.rsplit('/', 1)[-1])


# ─── PLAN ALIMENTARIO ────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def plan_nuevo(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = PlanAlimentarioForm(request.POST, request.FILES)
        if form.is_valid():
            plan = form.save(commit=False); plan.paciente = paciente; plan.save()
            messages.success(request, 'Plan alimentario guardado.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = PlanAlimentarioForm()
    return render(request, 'pacientes/plan_form.html', {'form': form, 'paciente': paciente, 'titulo': 'Nuevo plan alimentario'})


@login_required
@nutri_requerido
def plan_editar(request, nutri, pk, pid):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    plan = get_object_or_404(PlanAlimentario, pk=pid, paciente=paciente)
    if request.method == 'POST':
        form = PlanAlimentarioForm(request.POST, request.FILES, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plan actualizado.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = PlanAlimentarioForm(instance=plan)
    return render(request, 'pacientes/plan_form.html', {'form': form, 'paciente': paciente, 'plan': plan, 'titulo': 'Editar plan'})


@login_required
@nutri_requerido
def plan_descargar(request, nutri, pk, pid):
    """Sirve el PDF de un plan alimentario solo al nutricionista dueño del paciente."""
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    plan = get_object_or_404(PlanAlimentario, pk=pid, paciente=paciente)
    if not plan.archivo_pdf:
        raise Http404
    return FileResponse(plan.archivo_pdf.open('rb'), filename=plan.archivo_pdf.name.rsplit('/', 1)[-1])


# ─── ARCHIVOS ────────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def archivo_nuevo(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = ArchivoPacienteForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.save(commit=False); archivo.paciente = paciente; archivo.save()
            messages.success(request, 'Archivo subido.')
            return redirect(f"{reverse('paciente_detalle', args=[pk])}?tab=archivos")
    else:
        form = ArchivoPacienteForm()
    return render(request, 'pacientes/archivo_form.html', {'form': form, 'paciente': paciente, 'titulo': 'Subir archivo'})


@login_required
@nutri_requerido
def archivo_eliminar(request, nutri, pk, aid):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    archivo = get_object_or_404(ArchivoPaciente, pk=aid, paciente=paciente)
    if request.method == 'POST':
        archivo.archivo.delete(save=False)
        archivo.delete()
        messages.success(request, 'Archivo eliminado.')
    return redirect(f"{reverse('paciente_detalle', args=[pk])}?tab=archivos")


def archivo_ver(request, token):
    """
    Sirve un archivo de paciente por su token (UUID no adivinable). Sin login
    a propósito: es el link que se comparte con el paciente por WhatsApp, y el
    paciente no tiene cuenta. La seguridad acá es que el token es aleatorio de
    122 bits — no hay una URL /media/ pública ni un id secuencial adivinable.
    """
    archivo = get_object_or_404(ArchivoPaciente, token=token)
    if not archivo.archivo:
        raise Http404
    return FileResponse(archivo.archivo.open('rb'), filename=archivo.archivo.name.rsplit('/', 1)[-1])


# ─── CONSULTAS ───────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def consulta_nueva(request, nutri, pk):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = ConsultaForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False); c.paciente = paciente; c.save()
            messages.success(request, 'Consulta registrada.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = ConsultaForm()
    return render(request, 'pacientes/consulta_form.html', {'form': form, 'paciente': paciente, 'titulo': 'Nueva consulta'})


@login_required
@nutri_requerido
def consulta_editar(request, nutri, pk, cid):
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    consulta = get_object_or_404(Consulta, pk=cid, paciente=paciente)
    if request.method == 'POST':
        form = ConsultaForm(request.POST, instance=consulta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Consulta actualizada.')
            return redirect('paciente_detalle', pk=pk)
    else:
        form = ConsultaForm(instance=consulta)
    return render(request, 'pacientes/consulta_form.html', {'form': form, 'paciente': paciente, 'consulta': consulta, 'titulo': 'Editar consulta'})


# ─── AGENDA ──────────────────────────────────────────────────────────────────

@login_required
@nutri_requerido
def agenda(request, nutri):
    hoy = date.today()
    fecha_str = request.GET.get('fecha', hoy.isoformat())
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = hoy

    dias_semana = _semana_lun_sab(fecha)
    semana_inicio = dias_semana[0]
    semana_fin = dias_semana[-1]

    turnos_qs = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__date__gte=semana_inicio,
        fecha_hora_inicio__date__lte=semana_fin,
    ).select_related('paciente').order_by('fecha_hora_inicio')

    # Agrupar por dia
    turnos_por_dia = {d: [] for d in dias_semana}
    conteo_por_dia = {d: 0 for d in dias_semana}
    for t in turnos_qs:
        d = timezone.localtime(t.fecha_hora_inicio).date()
        if d in turnos_por_dia:
            turnos_por_dia[d].append(t)
            if t.estado in ('pendiente', 'confirmado'):
                conteo_por_dia[d] += 1

    return render(request, 'agenda/agenda.html', {
        'dias_semana': dias_semana,
        'semana_inicio': semana_inicio,
        'semana_fin': semana_fin,
        'turnos_por_dia': turnos_por_dia,
        'conteo_por_dia': conteo_por_dia,
        'hoy': hoy,
        'semana_anterior': (semana_inicio - timedelta(days=7)).isoformat(),
        'semana_siguiente': (semana_inicio + timedelta(days=7)).isoformat(),
    })


@login_required
@nutri_requerido
def turno_nuevo(request, nutri):
    if request.method == 'POST':
        form = TurnoForm(nutri, request.POST)
        if form.is_valid():
            turno = form.save(commit=False)
            turno.nutricionista = nutri
            sobreturno = turno.hay_sobreturno()
            turno.save()
            if sobreturno:
                messages.warning(request, 'Turno guardado, pero se detecto un posible sobreturno.')
            else:
                messages.success(request, 'Turno agendado correctamente.')
            return redirect('agenda')
    else:
        initial = {}
        fecha_str = request.GET.get('fecha')
        if fecha_str:
            initial['fecha_hora_inicio'] = fecha_str + 'T09:00'
        form = TurnoForm(nutri, initial=initial)
    return render(request, 'agenda/turno_form.html', {'form': form, 'titulo': 'Nuevo turno'})


@login_required
@nutri_requerido
def turno_editar(request, nutri, pk):
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = TurnoForm(nutri, request.POST, instance=turno)
        if form.is_valid():
            turno = form.save(commit=False)
            sobreturno = turno.hay_sobreturno()
            turno.save()
            if sobreturno:
                messages.warning(request, 'Turno actualizado, pero hay un posible sobreturno.')
            else:
                messages.success(request, 'Turno actualizado.')
            return redirect('agenda')
    else:
        form = TurnoForm(nutri, instance=turno)
    return render(request, 'agenda/turno_form.html', {'form': form, 'turno': turno, 'titulo': 'Editar turno'})


@login_required
@nutri_requerido
def turno_cancelar(request, nutri, pk):
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    turno.estado = 'cancelado'
    turno.save()
    messages.success(request, 'Turno cancelado.')
    return redirect('agenda')


@login_required
@nutri_requerido
def turno_repetir(request, nutri, pk):
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    nueva_fecha_sugerida = sumar_un_mes(turno.fecha_hora_inicio)

    if request.method == 'POST':
        fecha_str = request.POST.get('nueva_fecha', '')
        try:
            nueva_dt = datetime.fromisoformat(fecha_str)
            if timezone.is_naive(nueva_dt):
                nueva_dt = timezone.make_aware(nueva_dt)
            # Clonar el turno — el token tiene que ser nuevo, si no la base
            # rechaza el guardado porque ya existe otro turno con ese mismo
            # token (es único, se usa para el link público de reserva).
            turno.pk = None
            turno.token = uuid.uuid4()
            turno.fecha_hora_inicio = nueva_dt
            turno.estado = 'pendiente'
            turno.save()
            messages.success(request, f'Turno reagendado para el {nueva_dt.strftime("%d/%m/%Y a las %H:%M")}.')
        except (ValueError, TypeError):
            messages.error(request, 'Fecha invalida.')
        return redirect('agenda')

    return render(request, 'agenda/turno_repetir.html', {
        'turno': turno,
        'nueva_fecha': nueva_fecha_sugerida,
    })


# ─── RECORDATORIOS WHATSAPP ───────────────────────────────────────────────────

@login_required
@nutri_requerido
def recordatorios_hoy(request, nutri):
    hoy = timezone.localdate()
    turnos = (
        Turno.objects
        .filter(
            nutricionista=nutri,
            fecha_hora_inicio__date=hoy,
        )
        .exclude(estado='cancelado')
        .select_related('paciente')
        .order_by('fecha_hora_inicio')
    )
    # Adjuntar el número de teléfono limpio (solo dígitos) y el mensaje sugerido
    nombre_nutri = nutri.user.get_full_name() or 'tu nutricionista'
    plantilla = nutri.mensaje_recordatorio or Nutricionista.MENSAJE_RECORDATORIO_DEFAULT
    turnos_data = []
    for t in turnos:
        # timezone.localtime() es necesario: Django devuelve fecha_hora_inicio
        # en UTC al leerlo de la base, y strftime directo mostraría (y le
        # mandaría al paciente) una hora 3hs adelantada de la real.
        hora = timezone.localtime(t.fecha_hora_inicio).strftime('%H:%M')
        # Si el turno no tiene un Paciente vinculado (típico de una reserva
        # online de alguien nuevo), usamos los datos de contacto que esa
        # persona completó al reservar — si no, el recordatorio quedaba
        # inutilizable para todo turno nuevo que viniera del turnero.
        if t.paciente and t.paciente.telefono:
            nombre_para_mensaje = t.paciente.nombre
            telefono_crudo = t.paciente.telefono
        elif not t.paciente and t.telefono_contacto:
            nombre_para_mensaje = t.nombre_contacto
            telefono_crudo = t.telefono_contacto
        else:
            nombre_para_mensaje = ''
            telefono_crudo = ''

        if telefono_crudo:
            telefono_limpio = telefono_whatsapp_ar(telefono_crudo)
            link_confirmacion = request.build_absolute_uri(
                reverse('turno_confirmar_publico', kwargs={'token': t.token})
            )
            try:
                mensaje = plantilla.format(
                    nombre=nombre_para_mensaje, hora=hora, nutricionista=nombre_nutri,
                    link_confirmacion=link_confirmacion,
                )
            except Exception:
                # El texto es libre (lo escribe el nutricionista): una llave
                # inválida ({nombre_paciente}) tira KeyError, y llaves sueltas
                # como "{}" o "{0}" tiran IndexError — cualquier variante nos
                # tiene que caer acá sin romper la página, usamos el default.
                mensaje = Nutricionista.MENSAJE_RECORDATORIO_DEFAULT.format(
                    nombre=nombre_para_mensaje, hora=hora, nutricionista=nombre_nutri,
                    link_confirmacion=link_confirmacion,
                )
        else:
            telefono_limpio = ''
            mensaje = ''
        turnos_data.append({
            'turno': t,
            'hora': hora,
            'nombre': nombre_para_mensaje,
            'telefono_limpio': telefono_limpio,
            'mensaje': mensaje,
            'tiene_tel': bool(telefono_limpio),
        })
    return render(request, 'agenda/recordatorios.html', {
        'turnos_data': turnos_data,
        'hoy': hoy,
        'nutri': nutri,
        'hay_recordatorios': any(item['tiene_tel'] for item in turnos_data),
    })
