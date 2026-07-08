from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Nutricionista, Paciente, Turno, Medicion, Laboratorio, PlanAlimentario, Consulta
from .forms import (RegistroForm, PerfilForm, ContactoForm, PacienteForm, TurnoForm,
                    MedicionForm, LaboratorioForm, PlanAlimentarioForm, ConsultaForm)


# ─── PUBLICAS ─────────────────────────────────────────────────────────────────

def home(request):
    base_qs = Nutricionista.objects.filter(
        aprobado=True, user__is_active=True
    ).select_related('user', 'ciudad', 'ciudad__pais').prefetch_related('obras_sociales')
    destacados = list(base_qs.filter(destacado=True)[:6])
    # Si no hay destacados, mostrar los primeros 6 aprobados
    if not destacados:
        destacados = list(base_qs[:6])
    total_nutricionistas = base_qs.count()
    return render(request, 'home.html', {
        'destacados': destacados,
        'total_nutricionistas': total_nutricionistas,
    })


def nutricionistas_lista(request):
    from django.db.models import Q
    from .models import ObraSocial, Ciudad, Pais
    qs = Nutricionista.objects.filter(aprobado=True, user__is_active=True).select_related('user', 'ciudad', 'ciudad__pais').prefetch_related('obras_sociales')
    q = request.GET.get('q', '').strip()
    especialidad = request.GET.get('especialidad', '')
    edad = request.GET.get('edad', '')
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
        'q': q, 'especialidad': especialidad, 'edad': edad,
        'modalidad': modalidad, 'obra_social': obra_social, 'ciudad': ciudad, 'pais': pais,
        'especialidades': Nutricionista.ESPECIALIDADES,
        'edades': Nutricionista.EDADES,
        'modalidades': Nutricionista.MODALIDADES,
        'obras_sociales': ObraSocial.objects.filter(activa=True),
        'ciudades': Ciudad.objects.filter(activa=True),
        'paises': Pais.objects.filter(activo=True),
    })


def perfil_publico(request, slug):
    nutricionista = get_object_or_404(Nutricionista, slug=slug, aprobado=True)
    return render(request, 'perfil/publico.html', {'nutricionista': nutricionista})


def quiero_ser_parte(request):
    enviado = False
    plan_inicial = request.GET.get('plan', 'herramientas')
    if request.method == 'POST':
        form = ContactoForm(request.POST)
        if form.is_valid():
            from .models import ContactoInteresado
            cd = form.cleaned_data
            ContactoInteresado.objects.create(
                nombre=cd['nombre'], apellido=cd['apellido'],
                email=cd['email'], telefono=cd.get('telefono', ''),
                plan_interes=cd['plan_interes'],
            )
            planes = {
                'herramientas': 'Plan Completo (Publicidad + Herramientas)',
                'publicidad': 'Plan Básico (Solo publicidad)',
                'sin_definir': 'Sin definir',
            }
            cuerpo = (
                f"🆕 Nuevo interesado en NutricionClick\n\n"
                f"Nombre:    {cd['nombre']} {cd['apellido']}\n"
                f"Email:     {cd['email']}\n"
                f"WhatsApp:  {cd.get('telefono') or '—'}\n"
                f"Pacientes: {cd.get('pacientes_semana') or '—'}\n"
                f"Plan:      {planes.get(cd['plan_interes'], cd['plan_interes'])}\n"
            )
            try:
                send_mail(
                    subject=f"[NutricionClick] 🆕 {cd['nombre']} {cd['apellido']} — {planes.get(cd['plan_interes'], '')}",
                    message=cuerpo,
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
            messages.success(request, 'Registro exitoso. Tu cuenta sera revisada y recibiras un mail cuando este aprobada.')
            return redirect('login')
    else:
        form = RegistroForm()
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
    if nutri.tipo != 'premium':
        return redirect('home')

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
        d = t.fecha_hora_inicio.date()
        if d in conteo_por_dia:
            conteo_por_dia[d] += 1
    total_semana = sum(conteo_por_dia.values())

    proximos = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__gte=timezone.now(),
        estado__in=['pendiente', 'confirmado'],
    ).order_by('fecha_hora_inicio')[:5]

    total_pacientes = Paciente.objects.filter(nutricionista=nutri, activo=True).count()

    return render(request, 'dashboard/dashboard.html', {
        'nutri': nutri, 'hoy': hoy,
        'turnos_hoy': turnos_hoy,
        'total_pacientes': total_pacientes,
        'total_semana': total_semana,
        'proximos': proximos,
        'dias_semana': dias_semana,
        'conteo_por_dia': conteo_por_dia,
    })


@login_required
def perfil_editar(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    if request.method == 'POST':
        form = PerfilForm(request.POST, request.FILES, instance=nutri)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado.')
            return redirect('perfil_editar')
    else:
        form = PerfilForm(instance=nutri)
    return render(request, 'perfil/editar.html', {'form': form, 'nutri': nutri})


# ─── PACIENTES ────────────────────────────────────────────────────────────────

@login_required
def pacientes_lista(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def paciente_nuevo(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.nutricionista = nutri
            p.save()
            messages.success(request, f'Paciente {p.nombre_completo} agregado.')
            return redirect('paciente_detalle', pk=p.pk)
    else:
        form = PacienteForm()
    return render(request, 'pacientes/form.html', {'form': form, 'titulo': 'Nuevo paciente'})


@login_required
def paciente_editar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def paciente_detalle(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    tab = request.GET.get('tab', 'historia')
    mediciones = list(paciente.mediciones.all()[:20])
    mediciones_chart = list(reversed(mediciones))  # cronologico para el grafico
    laboratorios = paciente.laboratorios.all()[:10]
    planes = paciente.planes.all()[:10]
    consultas = paciente.consultas.all()[:10]
    ultima_medicion = mediciones[0] if mediciones else None
    return render(request, 'pacientes/detalle.html', {
        'paciente': paciente, 'nutri': nutri, 'tab': tab,
        'mediciones': mediciones, 'mediciones_chart': mediciones_chart,
        'laboratorios': laboratorios, 'planes': planes, 'consultas': consultas,
        'ultima_medicion': ultima_medicion,
    })


@login_required
def paciente_archivar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    paciente.activo = False
    paciente.save()
    messages.success(request, f'{paciente.nombre_completo} archivado.')
    return redirect('pacientes_lista')


# ─── MEDICIONES ──────────────────────────────────────────────────────────────

@login_required
def medicion_nueva(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def medicion_editar(request, pk, mid):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def laboratorio_nuevo(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def laboratorio_editar(request, pk, lid):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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


# ─── PLAN ALIMENTARIO ────────────────────────────────────────────────────────

@login_required
def plan_nuevo(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def plan_editar(request, pk, pid):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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


# ─── CONSULTAS ───────────────────────────────────────────────────────────────

@login_required
def consulta_nueva(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def consulta_editar(request, pk, cid):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def agenda(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
        d = t.fecha_hora_inicio.date()
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
def turno_nuevo(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def turno_editar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
def turno_cancelar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    turno.estado = 'cancelado'
    turno.save()
    messages.success(request, 'Turno cancelado.')
    return redirect('agenda')


@login_required
def turno_repetir(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    nueva_fecha_sugerida = turno.fecha_hora_inicio + timedelta(days=7)

    if request.method == 'POST':
        fecha_str = request.POST.get('nueva_fecha', '')
        try:
            nueva_dt = datetime.fromisoformat(fecha_str)
            if timezone.is_naive(nueva_dt):
                nueva_dt = timezone.make_aware(nueva_dt)
            # Clonar el turno
            turno.pk = None
            turno.fecha_hora_inicio = nueva_dt
            turno.estado = 'pendiente'
            turno.save()
            messages.success(request, f'Turno repetido para el {nueva_dt.strftime("%d/%m/%Y a las %H:%M")}.')
        except (ValueError, TypeError):
            messages.error(request, 'Fecha invalida.')
        return redirect('agenda')

    return render(request, 'agenda/turno_repetir.html', {
        'turno': turno,
        'nueva_fecha': nueva_fecha_sugerida,
    })


# ─── RECORDATORIOS WHATSAPP ───────────────────────────────────────────────────

@login_required
def recordatorios_hoy(request):
    nutri = get_object_or_404(Nutricionista, user=request.user, tipo='premium', aprobado=True)
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
    turnos_data = []
    for t in turnos:
        hora = t.fecha_hora_inicio.strftime('%H:%M')
        if t.paciente and t.paciente.telefono:
            telefono_limpio = ''.join(c for c in t.paciente.telefono if c.isdigit())
            mensaje = (
                f"Hola {t.paciente.nombre}, te recordamos tu turno de hoy "
                f"a las {hora} hs con {nombre_nutri}. ¡Te esperamos!"
            )
        else:
            telefono_limpio = ''
            mensaje = ''
        turnos_data.append({
            'turno': t,
            'hora': hora,
            'telefono_limpio': telefono_limpio,
            'mensaje': mensaje,
            'tiene_tel': bool(telefono_limpio),
        })
    return render(request, 'agenda/recordatorios.html', {
        'turnos_data': turnos_data,
        'hoy': hoy,
        'nutri': nutri,
    })
