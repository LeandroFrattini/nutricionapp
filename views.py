from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import Nutricionista, Paciente, Turno
from .forms import RegistroForm, PerfilForm, PacienteForm, TurnoForm


# ─── PÚBLICAS ────────────────────────────────────────────────────────────────

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    q = request.GET.get('q', '').strip()
    nutricionistas = Nutricionista.objects.filter(aprobado=True, user__is_active=True).select_related('user')
    if q:
        nutricionistas = nutricionistas.filter(
            user__first_name__icontains=q
        ) | nutricionistas.filter(
            user__last_name__icontains=q
        ) | nutricionistas.filter(
            especialidad__icontains=q
        )
    total_nutricionistas = Nutricionista.objects.filter(aprobado=True, user__is_active=True).count()
    return render(request, 'home.html', {
        'nutricionistas': nutricionistas,
        'total_nutricionistas': total_nutricionistas,
        'q': q,
    })


def registro(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Registro exitoso. Tu cuenta será revisada y recibirás un mail cuando esté aprobada.'
            )
            return redirect('login')
    else:
        form = RegistroForm()
    return render(request, 'registration/registro.html', {'form': form})


def perfil_publico(request, slug):
    nutricionista = get_object_or_404(Nutricionista, slug=slug, aprobado=True)
    return render(request, 'perfil/publico.html', {'nutricionista': nutricionista})


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    hoy = date.today()
    turnos_hoy = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__date=hoy,
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha_hora_inicio')
    total_pacientes = Paciente.objects.filter(nutricionista=nutri, activo=True).count()
    proximos = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__gte=datetime.now(),
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha_hora_inicio')[:5]
    return render(request, 'dashboard/dashboard.html', {
        'nutri': nutri,
        'turnos_hoy': turnos_hoy,
        'total_pacientes': total_pacientes,
        'proximos': proximos,
    })


# ─── PERFIL ──────────────────────────────────────────────────────────────────

@login_required
def perfil_editar(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=nutri)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil actualizado.')
            return redirect('perfil_editar')
    else:
        form = PerfilForm(instance=nutri)
    return render(request, 'perfil/editar.html', {'form': form, 'nutri': nutri})


# ─── PACIENTES ───────────────────────────────────────────────────────────────

@login_required
def pacientes_lista(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    q = request.GET.get('q', '')
    pacientes = Paciente.objects.filter(nutricionista=nutri, activo=True)
    if q:
        pacientes = pacientes.filter(
            nombre__icontains=q
        ) | pacientes.filter(apellido__icontains=q)
    pacientes = pacientes.order_by('apellido', 'nombre')

    if request.htmx:
        return render(request, 'pacientes/_lista_parcial.html', {'pacientes': pacientes, 'q': q})
    return render(request, 'pacientes/lista.html', {'pacientes': pacientes, 'q': q})


@login_required
def paciente_nuevo(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            paciente = form.save(commit=False)
            paciente.nutricionista = nutri
            paciente.save()
            messages.success(request, f'Paciente {paciente.nombre_completo} agregado.')
            return redirect('pacientes_lista')
    else:
        form = PacienteForm()
    return render(request, 'pacientes/form.html', {'form': form, 'titulo': 'Nuevo paciente'})


@login_required
def paciente_editar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = PacienteForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paciente actualizado.')
            return redirect('pacientes_lista')
    else:
        form = PacienteForm(instance=paciente)
    return render(request, 'pacientes/form.html', {
        'form': form,
        'paciente': paciente,
        'titulo': f'Editar — {paciente.nombre_completo}',
    })


@login_required
def paciente_archivar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    paciente = get_object_or_404(Paciente, pk=pk, nutricionista=nutri)
    paciente.activo = False
    paciente.save()
    messages.success(request, f'{paciente.nombre_completo} archivado.')
    return redirect('pacientes_lista')


# ─── AGENDA ──────────────────────────────────────────────────────────────────

@login_required
def agenda(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    hoy = date.today()
    fecha_str = request.GET.get('fecha', hoy.isoformat())
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = hoy

    turnos = Turno.objects.filter(
        nutricionista=nutri,
        fecha_hora_inicio__date=fecha
    ).order_by('fecha_hora_inicio')

    fecha_anterior = (fecha - timedelta(days=1)).isoformat()
    fecha_siguiente = (fecha + timedelta(days=1)).isoformat()

    return render(request, 'agenda/agenda.html', {
        'turnos': turnos,
        'fecha': fecha,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
        'hoy': hoy,
    })


@login_required
def turno_nuevo(request):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    sobreturno = False
    if request.method == 'POST':
        form = TurnoForm(nutri, request.POST)
        if form.is_valid():
            turno = form.save(commit=False)
            turno.nutricionista = nutri
            sobreturno = turno.hay_sobreturno()
            turno.save()
            if sobreturno:
                messages.warning(request, '⚠️ Turno guardado, pero se detectó un posible sobreturno.')
            else:
                messages.success(request, 'Turno agendado correctamente.')
            return redirect('agenda')
    else:
        # Pre-llenar fecha si viene de la agenda
        initial = {}
        fecha_str = request.GET.get('fecha')
        if fecha_str:
            initial['fecha_hora_inicio'] = fecha_str + 'T09:00'
        form = TurnoForm(nutri, initial=initial)
    return render(request, 'agenda/turno_form.html', {'form': form, 'titulo': 'Nuevo turno'})


@login_required
def turno_editar(request, pk):
    nutri = get_object_or_404(Nutricionista, user=request.user)
    turno = get_object_or_404(Turno, pk=pk, nutricionista=nutri)
    if request.method == 'POST':
        form = TurnoForm(nutri, request.POST, instance=turno)
        if form.is_valid():
            turno = form.save(commit=False)
            sobreturno = turno.hay_sobreturno()
            turno.save()
            if sobreturno:
                messages.warning(request, '⚠️ Turno actualizado, pero hay un posible sobreturno