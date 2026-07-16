"""
Suite de "salud del sitio": recorre TODAS las paginas relevantes (publicas,
dashboard del nutricionista, panel del dueno) con distintos estados de datos
(perfil completo, perfil vacio, sin turnero configurado, suspendido, oculto,
no aprobado) y falla si cualquiera tira un error no controlado.

Correr antes de cada deploy importante: python manage.py test core.tests_smoke
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone

from .models import (
    Nutricionista, Paciente, Turno, Pais, Provincia, Ciudad, ObraSocial,
    ConfiguracionTurnero, FranjaHoraria, Medicion, Laboratorio, PlanAlimentario,
    Consulta, CodigoDescuento, Egreso,
)


class AuditoriaSitioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nombre='Argentina', activo=True, codigo='AR')
        cls.provincia = Provincia.objects.create(nombre='Buenos Aires', pais=cls.pais, activa=True)
        cls.ciudad = Ciudad.objects.create(nombre='La Plata', pais=cls.pais, provincia=cls.provincia, activa=True)
        cls.os1 = ObraSocial.objects.create(nombre='OSDE', activa=True)

        cls.owner = User.objects.create_superuser(username='auditor_owner', password='x', email='a@a.com')

        # N1: premium, aprobado, perfil COMPLETO, turnero bien configurado
        u1 = User.objects.create_user(username='auditor_n1', password='x', first_name='Ana', last_name='Pérez')
        cls.n1 = Nutricionista.objects.create(
            user=u1, matricula='MP-1', tipo='premium', aprobado=True,
            fecha_aprobacion=date.today(), exento_de_pago=True,
            ciudad=cls.ciudad, pais=cls.pais, bio='Bio completa de prueba.',
            especialidades='clinica,deportiva', edades_atendidas='adultos,ninos',
            modalidad='ambas', telefono='2914250495', acepta_obras_sociales=True,
        )
        cls.n1.obras_sociales.add(cls.os1)
        cls.turnero1 = ConfiguracionTurnero.objects.create(
            nutricionista=cls.n1, activo=True, duracion_turno_minutos=30,
            precio_consulta=10000, requiere_sena=False,
        )
        FranjaHoraria.objects.create(turnero=cls.turnero1, dia_semana=0, hora_inicio='09:00', hora_fin='13:00')

        cls.paciente1 = Paciente.objects.create(
            nutricionista=cls.n1, nombre='Juan', apellido='Gómez',
            email='juan@example.com', telefono='2914112233',
        )
        cls.paciente_sin_tel = Paciente.objects.create(
            nutricionista=cls.n1, nombre='Sin', apellido='Telefono', email='sintel@example.com',
        )
        Medicion.objects.create(paciente=cls.paciente1, peso_kg=70)
        Laboratorio.objects.create(paciente=cls.paciente1)
        PlanAlimentario.objects.create(paciente=cls.paciente1)
        Consulta.objects.create(paciente=cls.paciente1)

        ahora = timezone.localtime()
        cls.turno1 = Turno.objects.create(
            nutricionista=cls.n1, paciente=cls.paciente1,
            fecha_hora_inicio=ahora.replace(hour=10, minute=0, second=0, microsecond=0),
            duracion_minutos=30, estado='pendiente',
        )
        Turno.objects.create(
            nutricionista=cls.n1, paciente=None,
            fecha_hora_inicio=ahora.replace(hour=11, minute=0, second=0, microsecond=0),
            duracion_minutos=30, estado='pendiente', origen='online',
            nombre_contacto='Carla', apellido_contacto='Ruiz', telefono_contacto='2914998877',
        )
        Turno.objects.create(
            nutricionista=cls.n1, paciente=None,
            fecha_hora_inicio=ahora.replace(hour=12, minute=0, second=0, microsecond=0),
            duracion_minutos=30, estado='pendiente',
        )

        # N2: premium, aprobado, perfil VACIO (sin foto, sin ciudad, sin bio,
        # sin especialidades, sin edades, sin obras sociales, sin telefono,
        # SIN ConfiguracionTurnero) — el caso mas propenso a romper templates
        # que asumen datos completos.
        u2 = User.objects.create_user(username='auditor_n2', password='x', first_name='', last_name='')
        cls.n2 = Nutricionista.objects.create(
            user=u2, matricula='', tipo='premium', aprobado=True,
            fecha_aprobacion=date.today(), exento_de_pago=True,
        )

        # N3: basico, aprobado
        u3 = User.objects.create_user(username='auditor_n3', password='x', first_name='Beto', last_name='Ríos')
        cls.n3 = Nutricionista.objects.create(
            user=u3, matricula='MP-3', tipo='base', aprobado=True,
            fecha_aprobacion=date.today(), exento_de_pago=True,
        )

        # N4: premium, NO aprobado (pendiente)
        u4 = User.objects.create_user(username='auditor_n4', password='x', first_name='Cami', last_name='Sosa')
        cls.n4 = Nutricionista.objects.create(user=u4, matricula='MP-4', tipo='premium', aprobado=False)

        # N5: premium, aprobado, OCULTO
        u5 = User.objects.create_user(username='auditor_n5', password='x', first_name='Dan', last_name='Vega')
        cls.n5 = Nutricionista.objects.create(
            user=u5, matricula='MP-5', tipo='premium', aprobado=True,
            fecha_aprobacion=date.today(), exento_de_pago=True, oculto=True,
        )

        # N6: premium, aprobado, SUSPENDIDO por pago (vencido hace 10 dias, no exento)
        u6 = User.objects.create_user(username='auditor_n6', password='x', first_name='Eli', last_name='Paz')
        cls.n6 = Nutricionista.objects.create(
            user=u6, matricula='MP-6', tipo='premium', aprobado=True,
            fecha_aprobacion=date.today() - timedelta(days=60),
            proxima_revision_pago=date.today() - timedelta(days=10),
            exento_de_pago=False,
        )

        # N7: premium, aprobado, turnero configurado pero INCOMPLETO
        # (requiere_sena=True sin precio_consulta -> no listo_para_publicar)
        u7 = User.objects.create_user(username='auditor_n7', password='x', first_name='Fer', last_name='Luna')
        cls.n7 = Nutricionista.objects.create(
            user=u7, matricula='MP-7', tipo='premium', aprobado=True,
            fecha_aprobacion=date.today(), exento_de_pago=True,
        )
        ConfiguracionTurnero.objects.create(
            nutricionista=cls.n7, activo=True, requiere_sena=True, precio_consulta=None,
        )

        CodigoDescuento.objects.create(codigo='AUDIT10', porcentaje_descuento=10, activo=True)

    def _assert_ok(self, client, url, allowed=(200, 302, 404), label=''):
        resp = client.get(url)
        self.assertIn(
            resp.status_code, allowed,
            f'{label or url} devolvio {resp.status_code} (esperaba uno de {allowed})'
        )
        return resp

    # ── PUBLICO, SIN LOGIN ──────────────────────────────────────────────
    def test_paginas_publicas(self):
        c = Client()
        self._assert_ok(c, '/', label='home')
        self._assert_ok(c, '/nutricionistas/', label='directorio')
        self._assert_ok(c, '/nutricionistas/?pais=' + str(self.pais.pk), label='directorio con pais')
        self._assert_ok(c, '/nutricionistas/?q=Ana&especialidad=clinica&edad=adultos&modalidad=ambas'
                            f'&obra_social={self.os1.pk}&ciudad={self.ciudad.pk}',
                         label='directorio con todos los filtros')
        self._assert_ok(c, '/quiero-ser-parte/', label='quiero ser parte')
        self._assert_ok(c, '/quiero-ser-parte/?plan=publicidad', label='quiero ser parte con plan')
        self._assert_ok(c, '/que-puedo-hacer/', label='que puedo hacer')
        self._assert_ok(c, '/registro/', label='registro')
        self._assert_ok(c, '/login/', label='login')
        self._assert_ok(c, '/portal/login/', label='portal login')
        self._assert_ok(c, '/password-reset/', label='password reset')
        self._assert_ok(c, '/robots.txt', label='robots.txt')

    def test_perfil_publico_todos_los_estados(self):
        """El caso clave: 'Ver como me ven' para cada tipo de perfil."""
        c = Client()
        # Visible, perfil completo
        self._assert_ok(c, f'/nutricionistas/{self.n1.slug}/', allowed=(200,), label='perfil publico N1 (completo)')
        # Visible, perfil VACIO — el caso mas probable de romperse
        self._assert_ok(c, f'/nutricionistas/{self.n2.slug}/', allowed=(200,), label='perfil publico N2 (vacio)')
        # Visible, basico
        self._assert_ok(c, f'/nutricionistas/{self.n3.slug}/', allowed=(200,), label='perfil publico N3 (basico)')
        # NO deberian mostrarse (404 controlado esta bien, 500 no)
        self._assert_ok(c, f'/nutricionistas/{self.n4.slug}/', allowed=(404,), label='perfil publico N4 (pendiente)')
        self._assert_ok(c, f'/nutricionistas/{self.n5.slug}/', allowed=(404,), label='perfil publico N5 (oculto)')
        self._assert_ok(c, f'/nutricionistas/{self.n6.slug}/', allowed=(404,), label='perfil publico N6 (suspendido)')

    def test_confirmar_turno_publico(self):
        c = Client()
        self._assert_ok(c, f'/turnero/turno/{self.turno1.token}/confirmar/', allowed=(200,), label='confirmar turno')

    def test_ver_como_me_ven_siempre_funciona_para_el_propio_nutri(self):
        """'Ver como me ven' desde el propio dashboard nunca debe romperse,
        aunque el perfil no cumpla los requisitos para ser publico (oculto,
        pendiente de aprobar o suspendido por pago) — debe avisar por que,
        no tirar un 404 sin explicacion."""
        for n, label in [(self.n4, 'pendiente'), (self.n5, 'oculto'), (self.n6, 'suspendido')]:
            c = Client()
            c.force_login(n.user)
            resp = self._assert_ok(c, f'/nutricionistas/{n.slug}/', allowed=(200,),
                                    label=f'ver como me ven — {label}')
            self.assertContains(resp, 'adelanto', msg_prefix=f'({label})')

    def test_turnero_reservar_publico(self):
        c = Client()
        self._assert_ok(c, f'/reservar/{self.n1.slug}/', allowed=(200,), label='reservar N1 (bien configurado)')
        self._assert_ok(c, f'/reservar/{self.n2.slug}/', allowed=(404,), label='reservar N2 (sin turnero)')
        self._assert_ok(c, f'/reservar/{self.n7.slug}/', allowed=(404,), label='reservar N7 (turnero incompleto)')

    # ── DASHBOARD DEL NUTRICIONISTA ─────────────────────────────────────
    def test_dashboard_nutricionista_perfil_completo(self):
        c = Client()
        c.force_login(self.n1.user)
        self._assert_ok(c, '/dashboard/', allowed=(200,), label='dashboard N1')
        self._assert_ok(c, '/dashboard/perfil/', allowed=(200,), label='perfil editar N1')
        self._assert_ok(c, '/dashboard/pacientes/', allowed=(200,), label='pacientes N1')
        self._assert_ok(c, f'/dashboard/pacientes/{self.paciente1.pk}/', allowed=(200,), label='paciente detalle')
        self._assert_ok(c, f'/dashboard/pacientes/{self.paciente1.pk}/editar/', allowed=(200,), label='paciente editar')
        self._assert_ok(c, f'/dashboard/pacientes/{self.paciente_sin_tel.pk}/', allowed=(200,), label='paciente sin telefono')
        self._assert_ok(c, '/dashboard/pacientes/nuevo/', allowed=(200,), label='paciente nuevo')
        self._assert_ok(c, '/dashboard/agenda/', allowed=(200,), label='agenda N1')
        self._assert_ok(c, '/dashboard/agenda/turno/nuevo/', allowed=(200,), label='turno nuevo')
        self._assert_ok(c, '/dashboard/recordatorios/', allowed=(200,), label='recordatorios N1')
        self._assert_ok(c, '/dashboard/turnero/', allowed=(200,), label='turnero config N1')
        self._assert_ok(c, '/dashboard/cambiar-password/', allowed=(200,), label='cambiar password')

    def test_dashboard_nutricionista_perfil_vacio(self):
        """N2 no tiene NADA cargado — es el escenario mas parecido a un
        nutricionista recien aprobado que todavia no completo su perfil."""
        c = Client()
        c.force_login(self.n2.user)
        self._assert_ok(c, '/dashboard/', allowed=(200,), label='dashboard N2 (vacio)')
        self._assert_ok(c, '/dashboard/perfil/', allowed=(200,), label='perfil editar N2 (vacio)')
        self._assert_ok(c, '/dashboard/pacientes/', allowed=(200,), label='pacientes N2 (vacio)')
        self._assert_ok(c, '/dashboard/agenda/', allowed=(200,), label='agenda N2 (vacio)')
        self._assert_ok(c, '/dashboard/recordatorios/', allowed=(200,), label='recordatorios N2 (vacio)')
        self._assert_ok(c, '/dashboard/turnero/', allowed=(200,), label='turnero config N2 (sin configurar)')

    def test_dashboard_basico_redirige(self):
        c = Client()
        c.force_login(self.n3.user)
        self._assert_ok(c, '/dashboard/', allowed=(200, 302), label='dashboard N3 (basico)')
        self._assert_ok(c, '/dashboard/perfil/', allowed=(200,), label='perfil editar N3 (basico)')

    def test_dashboard_no_aprobado_va_a_en_revision(self):
        c = Client()
        c.force_login(self.n4.user)
        self._assert_ok(c, '/dashboard/', allowed=(200, 302), label='dashboard N4 (pendiente)')
        self._assert_ok(c, '/dashboard/en-revision/', allowed=(200,), label='en revision')

    def test_dashboard_suspendido_por_pago(self):
        c = Client()
        c.force_login(self.n6.user)
        self._assert_ok(c, '/dashboard/', allowed=(200, 302), label='dashboard N6 (suspendido)')
        self._assert_ok(c, '/dashboard/perfil-suspendido/', allowed=(200,), label='perfil suspendido')
        self._assert_ok(c, '/dashboard/renovar/', allowed=(200,), label='renovar')

    # ── PANEL DEL DUENO ─────────────────────────────────────────────────
    def test_panel_dueno(self):
        c = Client()
        c.force_login(self.owner)
        self._assert_ok(c, '/mi-panel/', allowed=(200,), label='panel resumen')
        self._assert_ok(c, '/mi-panel/nutricionistas/', allowed=(200,), label='panel nutricionistas')
        self._assert_ok(c, '/mi-panel/nutricionistas/nuevo/', allowed=(200,), label='panel nutricionista nuevo')
        self._assert_ok(c, '/mi-panel/pacientes/', allowed=(200,), label='panel pacientes')
        self._assert_ok(c, '/mi-panel/codigos/', allowed=(200,), label='panel codigos')
        self._assert_ok(c, '/mi-panel/codigos/nuevo/', allowed=(200,), label='panel codigo nuevo')
        for n in [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6, self.n7]:
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/editar/', allowed=(200,), label=f'panel editar {n.pk}')
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/cambiar-password/', allowed=(200,), label=f'panel password {n.pk}')
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/tarjeta/', allowed=(200,), label=f'panel tarjeta {n.pk}')

    def test_panel_resumen_con_egresos_no_rompe(self):
        """El calculo de ganancia neta mezclaba float y Decimal — rompia el
        resumen del dueno apenas habia un egreso cargado este mes."""
        Egreso.objects.create(concepto='Hosting', monto=1500)
        c = Client()
        c.force_login(self.owner)
        self._assert_ok(c, '/mi-panel/', allowed=(200,), label='panel resumen con egresos')

    def test_panel_blanquear_password_paciente(self):
        c = Client()
        c.force_login(self.owner)
        resp = self._assert_ok(c, f'/mi-panel/pacientes/{self.paciente1.pk}/blanquear-password/',
                                allowed=(302,), label='blanquear password')
