"""
Suite de "salud del sitio": recorre TODAS las paginas relevantes (publicas,
dashboard del nutricionista, panel del dueno) con distintos estados de datos
(perfil completo, perfil vacio, sin turnero configurado, suspendido, oculto,
no aprobado) y falla si cualquiera tira un error no controlado.

Correr antes de cada deploy importante: python manage.py test core.tests_smoke
"""
from datetime import date, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, Client
from django.utils import timezone

from .models import (
    Nutricionista, Paciente, Turno, Pais, Provincia, Ciudad, ObraSocial,
    ConfiguracionTurnero, FranjaHoraria, Medicion, Laboratorio, PlanAlimentario,
    Consulta, CodigoDescuento, Egreso, ContactoInteresado, PagoSuscripcion,
)
from . import mercadopago_suscripciones as mp_susc


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
            especialidades='clinica,deportiva,otra', edades_atendidas='adultos,ninos',
            composicion_corporal='isak1,bioimpedancia', especialidad_otra='Nutrición oncológica',
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

        cls.lead1 = ContactoInteresado.objects.create(
            nombre='Gina', apellido='Torres', email='gina@example.com',
            telefono='2914001122', pais=cls.pais, plan_interes='herramientas', contactado=False,
        )
        cls.lead2 = ContactoInteresado.objects.create(
            nombre='Hugo', apellido='Ibarra', email='hugo@example.com',
            plan_interes='publicidad', contactado=True,
        )

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
                            f'&obra_social={self.os1.pk}&ciudad={self.ciudad.pk}&composicion=isak1',
                         label='directorio con todos los filtros')
        self._assert_ok(c, '/quiero-ser-parte/', label='quiero ser parte')
        self._assert_ok(c, '/quiero-ser-parte/?plan=publicidad', label='quiero ser parte con plan')
        self._assert_ok(c, '/que-puedo-hacer/', label='que puedo hacer')
        self._assert_ok(c, '/registro/', label='registro')
        self._assert_ok(c, '/login/', label='login')
        self._assert_ok(c, '/portal/login/', label='portal login')
        self._assert_ok(c, '/password-reset/', label='password reset')
        self._assert_ok(c, '/robots.txt', label='robots.txt')

    def test_quiero_ser_parte_tiene_video_explicativo(self):
        resp = self._assert_ok(Client(), '/quiero-ser-parte/', label='quiero ser parte')
        self.assertContains(resp, 'youtube.com/embed/qN3S7sBe_r8')

    def test_quiero_ser_parte_guarda_telefono_opcional(self):
        """El form de "quiero ser parte" pide WhatsApp ademas del mail
        (opcional) — se guarda en ContactoInteresado y despues aparece con
        boton de WhatsApp en /mi-panel/leads/."""
        c = Client()
        resp = c.post('/quiero-ser-parte/', {
            'email': 'lead_smoke@example.com', 'telefono': '2914005566', 'plan_interes': 'herramientas',
        })
        self.assertEqual(resp.status_code, 200)
        lead = ContactoInteresado.objects.get(email='lead_smoke@example.com')
        self.assertEqual(lead.telefono, '2914005566')

        # tambien tiene que funcionar sin telefono (es opcional)
        resp = c.post('/quiero-ser-parte/', {
            'email': 'lead_smoke_sin_tel@example.com', 'telefono': '', 'plan_interes': 'publicidad',
        })
        self.assertEqual(resp.status_code, 200)

        c2 = Client()
        c2.force_login(self.owner)
        resp = c2.get('/mi-panel/leads/?estado=todos')
        self.assertContains(resp, 'wa.me/2914005566')

    def test_perfil_publico_todos_los_estados(self):
        """El caso clave: 'Ver como me ven' para cada tipo de perfil."""
        c = Client()
        # Visible, perfil completo
        resp = self._assert_ok(c, f'/nutricionistas/{self.n1.slug}/', allowed=(200,), label='perfil publico N1 (completo)')
        self.assertContains(resp, 'Antropometría ISAK I')
        # "Otra" con texto propio se muestra como el texto, no como "Otra"
        self.assertContains(resp, 'Nutrición oncológica')
        self.assertNotContains(resp, '>Otra<')
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

    def test_agenda_boton_reagendar_claro_y_fila_responsive(self):
        """El icono de flechita circular para reagendar no se entendía —
        tiene que ser un botón con el texto "Reagendar" bien visible. Y la
        fila del turno tiene que poder pasar a 2 líneas en mobile (flex-wrap
        + basis-full en las acciones) para que el nombre del paciente no
        empuje/pise el badge de estado y los botones en pantallas angostas
        (probado a mano en un viewport de iPhone: sin este fix, un nombre
        largo terminaba superpuesto con el badge "Confirmado")."""
        c = Client()
        c.force_login(self.n1.user)
        resp = self._assert_ok(c, '/dashboard/agenda/', allowed=(200,), label='agenda N1')
        cuerpo = resp.content.decode()
        self.assertIn('Reagendar', cuerpo)
        self.assertNotIn('Repetir en 7 dias', cuerpo)
        self.assertIn('flex-wrap', cuerpo)
        self.assertIn('basis-full', cuerpo)

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
        resp = self._assert_ok(c, '/mi-panel/', allowed=(200,), label='panel resumen')
        self.assertContains(resp, 'href="/mi-panel/leads/"')
        resp = self._assert_ok(c, '/mi-panel/nutricionistas/', allowed=(200,), label='panel nutricionistas')
        self.assertContains(resp, 'Copiar link')
        self._assert_ok(c, '/mi-panel/nutricionistas/nuevo/', allowed=(200,), label='panel nutricionista nuevo')
        self._assert_ok(c, '/mi-panel/pacientes/', allowed=(200,), label='panel pacientes')
        self._assert_ok(c, '/mi-panel/codigos/', allowed=(200,), label='panel codigos')
        self._assert_ok(c, '/mi-panel/codigos/nuevo/', allowed=(200,), label='panel codigo nuevo')
        for n in [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6, self.n7]:
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/editar/', allowed=(200,), label=f'panel editar {n.pk}')
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/cambiar-password/', allowed=(200,), label=f'panel password {n.pk}')
            self._assert_ok(c, f'/mi-panel/nutricionistas/{n.pk}/tarjeta/', allowed=(200,), label=f'panel tarjeta {n.pk}')

    def test_panel_leads(self):
        """El link "Leads sin contactar" del dashboard tiene que llevar a una
        pagina real con el listado (antes no existia ninguna pagina para
        verlos, ni en el panel ni en /admin/)."""
        c = Client()
        c.force_login(self.owner)
        resp = self._assert_ok(c, '/mi-panel/leads/', allowed=(200,), label='panel leads (default: pendientes)')
        self.assertContains(resp, 'Gina Torres')
        self.assertNotContains(resp, 'Hugo Ibarra')
        self.assertContains(resp, 'wa.me/2914001122')

        resp = self._assert_ok(c, '/mi-panel/leads/?estado=todos', allowed=(200,), label='panel leads (todos)')
        self.assertContains(resp, 'Gina Torres')
        self.assertContains(resp, 'Hugo Ibarra')

        c.post(f'/mi-panel/leads/{self.lead1.pk}/toggle-contactado/')
        self.lead1.refresh_from_db()
        self.assertTrue(self.lead1.contactado)

    def test_admin_django_muestra_todos_los_campos_csv(self):
        """Cada campo tipo "checkboxes guardados como CSV" (especialidades,
        edades, composicion_corporal) tiene que estar en el fieldset del
        admin de Django — si falta, el campo queda invisible en /admin/ aunque
        el modelo y el formulario lo soporten (paso 2 veces con
        composicion_corporal y especialidad_otra)."""
        c = Client()
        c.force_login(self.owner)
        resp = self._assert_ok(
            c, f'/{settings.ADMIN_URL}core/nutricionista/{self.n1.pk}/change/',
            allowed=(200,), label='admin nutricionista change',
        )
        self.assertContains(resp, 'name="composicion_corporal"')
        self.assertContains(resp, 'name="especialidad_otra"')

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

    def test_codigo_descuento_calcula_monto_correcto(self):
        """El % del código de descuento tiene que descontarse bien del precio
        de lista, solo sobre el primer mes, y nunca combinarse con el
        descuento por volumen de pagar varios meses juntos."""
        codigo_10 = CodigoDescuento.objects.get(codigo='AUDIT10')  # creado en setUpTestData, 10%
        codigo_50 = CodigoDescuento.objects.create(codigo='MITAD50', porcentaje_descuento=50, activo=True)
        codigo_100 = CodigoDescuento.objects.create(codigo='GRATIS100', porcentaje_descuento=100, activo=True)

        precio_base = mp_susc.precio_mensual('base')       # 15000
        precio_premium = mp_susc.precio_mensual('premium')  # 40000

        # 10% de descuento sobre el primer mes, para ambos planes
        self.assertEqual(mp_susc.monto_por_meses('base', 1, codigo_10), round(precio_base * 0.9, 2))
        self.assertEqual(mp_susc.monto_por_meses('premium', 1, codigo_10), round(precio_premium * 0.9, 2))

        # 50% y 100% (gratis) tienen que descontarse igual de bien, no solo el 10%
        self.assertEqual(mp_susc.monto_por_meses('premium', 1, codigo_50), round(precio_premium * 0.5, 2))
        self.assertEqual(mp_susc.monto_por_meses('premium', 1, codigo_100), 0)

        # Sin código, se cobra el precio de lista completo
        self.assertEqual(mp_susc.monto_por_meses('premium', 1, None), precio_premium)

        # El código NUNCA se aplica si se pagan varios meses juntos (regla de
        # negocio: es exclusivo del primer pago) — tiene que cobrar el
        # descuento por VOLUMEN normal, ignorando el código por completo.
        monto_3_meses_con_codigo = mp_susc.monto_por_meses('premium', 3, codigo_100)
        monto_3_meses_sin_codigo = mp_susc.monto_por_meses('premium', 3, None)
        self.assertEqual(monto_3_meses_con_codigo, monto_3_meses_sin_codigo)
        self.assertGreater(monto_3_meses_con_codigo, 0)

    def test_codigo_descuento_de_punta_a_punta_en_el_registro(self):
        """Simula a un nutricionista registrandose de verdad con un código de
        descuento activo: el pago que se genera al final tiene que tener el
        monto ya descontado, no el precio de lista."""
        codigo = CodigoDescuento.objects.get(codigo='AUDIT10')  # 10%
        c = Client()
        # Simula que la cuenta de Mercado Pago de la plataforma esta
        # configurada (si no, la vista corta antes de crear el PagoSuscripcion)
        # pero sin llamar de verdad a la API externa de MP durante el test.
        with mock.patch.object(settings, 'MP_ACCESS_TOKEN_PLATAFORMA', 'token-de-prueba'), \
             mock.patch.object(mp_susc, 'crear_pago', return_value=None):
            resp = c.post('/registro/', {
                'username': 'nutri_con_descuento', 'first_name': 'Con', 'last_name': 'Descuento',
                'email': 'condescuento@example.com', 'matricula': 'MP-DESC',
                'pais': self.pais.pk, 'plan_suscripcion': 'premium',
                'codigo_descuento': codigo.codigo,
                'password1': 'unaClaveSegura123', 'password2': 'unaClaveSegura123',
            }, follow=True)
        self.assertEqual(resp.status_code, 200)

        nutri = Nutricionista.objects.get(user__username='nutri_con_descuento')
        self.assertEqual(nutri.codigo_descuento_usado, codigo)

        pago = PagoSuscripcion.objects.get(nutricionista=nutri)
        self.assertEqual(pago.monto, round(mp_susc.precio_mensual('premium') * 0.9, 2))

    def test_ingreso_estimado_refleja_el_codigo_de_descuento(self):
        """El ingreso mensual estimado del panel usaba siempre el precio de
        lista completo, ignorando que el primer pago se haya cobrado con
        descuento — tiene que reflejar lo que de verdad se cobró."""
        from .views_panel import _ingreso_mensual_estimado

        codigo15 = CodigoDescuento.objects.create(codigo='QUINCE15', porcentaje_descuento=15, activo=True)
        u = User.objects.create_user(username='nutri_desc_ingreso', password='x', first_name='D', last_name='I')
        nutri = Nutricionista.objects.create(
            user=u, matricula='MP-ING', tipo='base', aprobado=True,
            fecha_aprobacion=date.today(), codigo_descuento_usado=codigo15,
        )
        monto_con_descuento = round(mp_susc.precio_mensual('base') * 0.85, 2)
        PagoSuscripcion.objects.create(
            nutricionista=nutri, meses=1, monto=monto_con_descuento,
            confirmado=True, confirmado_en=timezone.now(),
        )
        self.assertEqual(_ingreso_mensual_estimado(nutri), monto_con_descuento)
        self.assertNotEqual(_ingreso_mensual_estimado(nutri), mp_susc.precio_mensual('base'))

    def test_codigo_descuento_usados_no_cuenta_registros_abandonados(self):
        """Si alguien intenta registrarse varias veces con el mismo código
        pero solo una vez termina de pagar, "usados" tiene que mostrar 1, no
        la cantidad de intentos de registro (cada intento crea un
        Nutricionista nuevo, hayan pagado o no)."""
        codigo = CodigoDescuento.objects.create(codigo='TRESVECES', porcentaje_descuento=20, activo=True)

        # intento con pago exitoso
        u1 = User.objects.create_user(username='intento_pago_ok', password='x')
        n1 = Nutricionista.objects.create(
            user=u1, matricula='MP-OK', tipo='base', aprobado=True, codigo_descuento_usado=codigo,
        )
        PagoSuscripcion.objects.create(
            nutricionista=n1, meses=1, monto=1000, confirmado=True, confirmado_en=timezone.now(),
        )

        # intentos abandonados: nunca pagaron, quedan sin aprobar
        for i in range(2):
            u = User.objects.create_user(username=f'intento_abandonado_{i}', password='x')
            Nutricionista.objects.create(
                user=u, matricula=f'MP-AB{i}', tipo='base', aprobado=False, codigo_descuento_usado=codigo,
            )

        # caso borde: aprobado a mano por el dueño pero sin pago confirmado
        # (tampoco debería contar como "uso" real del código)
        u_manual = User.objects.create_user(username='aprobado_manual_sin_pago', password='x')
        Nutricionista.objects.create(
            user=u_manual, matricula='MP-MANUAL', tipo='base', aprobado=True, codigo_descuento_usado=codigo,
        )

        c = Client()
        c.force_login(self.owner)
        resp = self._assert_ok(c, '/mi-panel/codigos/', allowed=(200,), label='panel codigos')
        codigo_en_pagina = next(cod for cod in resp.context['codigos'] if cod.pk == codigo.pk)
        self.assertEqual(codigo_en_pagina.usados_este_mes, 1)
        self.assertEqual(codigo_en_pagina.activos_totales, 1)

    def test_mail_bienvenida_usa_el_dominio_real_no_localhost(self):
        """El mail de "cuenta aprobada" tenía el link de ingreso hardcodeado a
        http://localhost:8000/login/ en el template — nunca usaba SITE_URL,
        asi que en producción mandaba a los nutris a su propia máquina en
        vez del sitio real."""
        from .emails import enviar_bienvenida
        u = User.objects.create_user(username='nutri_bienvenida', password='x', email='nutri@example.com')
        nutri = Nutricionista.objects.create(user=u, matricula='MP-BIEN', tipo='base')
        with mock.patch.object(settings, 'SITE_URL', 'https://nutricionclick.com'):
            enviar_bienvenida(nutri)
        self.assertEqual(len(mail.outbox), 1)
        cuerpo_html = mail.outbox[0].alternatives[0][0]
        self.assertIn('https://nutricionclick.com/login/', cuerpo_html)
        self.assertNotIn('localhost', cuerpo_html)

    def test_pago_confirmado_activa_el_usuario_y_puede_loguearse(self):
        """BUG CRÍTICO: al registrarse, el usuario queda con is_active=False
        (correcto, hasta que se apruebe). Cuando Mercado Pago confirma el
        pago automáticamente (el camino normal de CUALQUIER registro
        público), se ponía nutricionista.aprobado=True pero NUNCA se
        activaba el User de Django — el toggle manual del dueño en el panel
        sí lo hacía, pero el pago automático no. Resultado: la cuenta se veía
        "Activa" en el panel, pero ninguna contraseña la dejaba entrar nunca,
        porque Django rechaza el login de un usuario con is_active=False
        pase lo que pase con la contraseña."""
        from .views_pago import _confirmar_pago

        c = Client()
        # mp_susc.configurado() depende de si HAY credenciales reales de
        # Mercado Pago cargadas en el .env de esta máquina — si las hay (como
        # en desarrollo local para probar el checkout de verdad),
        # registro_pagar() arma un link real y redirige a
        # www.mercadopago.com.ar, y el follow=True de más abajo intenta
        # seguirlo y explota con DisallowedHost (no es un host de este sitio).
        # Lo forzamos a False para que este test sea determinístico sin
        # importar qué .env tenga la máquina que lo corre — lo que se prueba
        # acá es el paso SIGUIENTE (confirmación de pago), no el checkout.
        with mock.patch.object(mp_susc, 'configurado', return_value=False):
            resp = c.post('/registro/', {
                'username': 'nutri_recien_pagado', 'first_name': 'Recien', 'last_name': 'Pagado',
                'email': 'recienpagado@example.com', 'matricula': 'MP-PAGO',
                'pais': self.pais.pk, 'plan_suscripcion': 'premium',
                'codigo_descuento': '',
                'password1': 'unaClaveSegura123', 'password2': 'unaClaveSegura123',
            }, follow=True)
        self.assertEqual(resp.status_code, 200)

        nutri = Nutricionista.objects.get(user__username='nutri_recien_pagado')
        self.assertFalse(nutri.aprobado)
        self.assertFalse(nutri.user.is_active)  # correcto: todavia no pago nada

        pago = PagoSuscripcion.objects.create(nutricionista=nutri, meses=1, monto=40000)
        with mock.patch.object(mp_susc, 'pago_fue_aprobado', return_value=True):
            acredito_ahora = _confirmar_pago(pago)
        self.assertTrue(acredito_ahora)

        nutri.refresh_from_db()
        self.assertTrue(nutri.aprobado)
        self.assertTrue(nutri.user.is_active, 'is_active tiene que quedar True al confirmarse el pago')

        # La prueba real: que efectivamente pueda loguearse con su contraseña.
        # Client.login() no sirve acá: AxesBackend exige un `request` real
        # para autenticar, asi que se hace un POST de verdad al form de
        # /login/ en vez de authenticate() suelto.
        c2 = Client()
        resp2 = c2.post('/login/', {'username': 'nutri_recien_pagado', 'password': 'unaClaveSegura123'})
        self.assertEqual(resp2.status_code, 302, 'el nutricionista tiene que poder loguearse despues de que se confirme el pago')

    def test_login_funciona_aunque_haya_dos_cuentas_con_el_mismo_email(self):
        """El email no tiene restriccion de unicidad en la base, asi que
        pueden existir dos Users con el mismo email (ej. alguien se registro
        dos veces). Antes, EmailOrUsernameBackend usaba .get() y con mas de
        un resultado tiraba MultipleObjectsReturned -> login SIEMPRE
        invalido para ese email, con contraseña correcta o no. Ahora tiene
        que entrar igual, como el usuario que realmente coincide."""
        User.objects.create_user(
            username='cuenta_abandonada', email='mismoemail@example.com', password='otraClave456',
        )
        User.objects.create_user(
            username='cuenta_real', email='MismoEmail@example.com', password='miClaveVerdadera789',
            is_active=True,
        )
        # Client.login() no sirve acá: AxesBackend exige un `request` real
        # para autenticar, así que se prueba con un POST de verdad al form
        # de /login/ (que sí pasa el request), en vez de authenticate() suelto.
        c = Client()
        resp = c.post('/login/', {'username': 'mismoemail@example.com', 'password': 'miClaveVerdadera789'})
        self.assertEqual(resp.status_code, 302, 'tiene que poder entrar con el email aunque haya otra cuenta con el mismo email')

    def test_registro_publico_rechaza_email_duplicado(self):
        """Antes, RegistroForm no validaba el email para nada (solo Django
        exige que el USERNAME sea unico) — asi fue como alguien pudo
        registrarse 3 veces con el mismo email sin ningun aviso, generando
        cuentas duplicadas que rompen el login (ver test de arriba)."""
        User.objects.create_user(username='ya_existente', email='repetido@example.com', password='x')
        c = Client()
        resp = c.post('/registro/', {
            'username': 'intento_nuevo', 'first_name': 'Intento', 'last_name': 'Nuevo',
            'email': 'REPETIDO@example.com', 'matricula': 'MP-DUP',
            'pais': self.pais.pk, 'plan_suscripcion': 'premium', 'codigo_descuento': '',
            'password1': 'unaClaveSegura123', 'password2': 'unaClaveSegura123',
        })
        self.assertEqual(resp.status_code, 200)  # se queda en la pagina con el error, no redirige
        self.assertFalse(User.objects.filter(username='intento_nuevo').exists())
        self.assertContains(resp, 'Ya hay una cuenta registrada con ese email')

    def test_panel_reparar_logins_arregla_cuentas_bloqueadas(self):
        """Corrige de una sola vez a los nutricionistas que ya habian quedado
        atrapados por el bug de is_active (aprobados pero sin poder
        loguearse) y a los que quedaron aprobados sin ningun vencimiento
        cargado, sin tocar a los que estan bien."""
        from .utils import sumar_un_mes

        u_bloqueada = User.objects.create_user(
            username='bloqueada_por_bug', email='bloqueada@example.com', password='x', is_active=False,
        )
        n_bloqueada = Nutricionista.objects.create(user=u_bloqueada, matricula='MP-BLOQ', aprobado=True)

        # control: nutri no aprobado, no debe tocarse aunque is_active sea False
        u_pendiente = User.objects.create_user(
            username='pendiente_normal', email='pendiente@example.com', password='x', is_active=False,
        )
        Nutricionista.objects.create(user=u_pendiente, matricula='MP-PEND', aprobado=False)

        # aprobada a mano hace tiempo, sin ningun vencimiento cargado
        u_sin_venc = User.objects.create_user(username='sin_vencimiento', password='x', is_active=True)
        n_sin_venc = Nutricionista.objects.create(user=u_sin_venc, matricula='MP-SINV', aprobado=True)

        # control: exenta de pago, no deberia recibir vencimiento
        u_exenta = User.objects.create_user(username='exenta_control', password='x', is_active=True)
        n_exenta = Nutricionista.objects.create(
            user=u_exenta, matricula='MP-EXCTRL', aprobado=True, exento_de_pago=True,
        )

        # control: ya tenia un vencimiento real, no se le tiene que tocar
        u_con_venc = User.objects.create_user(username='con_vencimiento', password='x', is_active=True)
        vencimiento_real = date.today() + timedelta(days=200)
        n_con_venc = Nutricionista.objects.create(
            user=u_con_venc, matricula='MP-CONV', aprobado=True, proxima_revision_pago=vencimiento_real,
        )

        c = Client()
        c.force_login(self.owner)
        resp = c.post('/mi-panel/nutricionistas/reparar-logins/', follow=True)
        self.assertEqual(resp.status_code, 200)

        n_bloqueada.refresh_from_db()
        u_pendiente.refresh_from_db()
        n_sin_venc.refresh_from_db()
        n_exenta.refresh_from_db()
        n_con_venc.refresh_from_db()

        self.assertTrue(n_bloqueada.user.is_active, 'la cuenta aprobada pero bloqueada tiene que quedar activa')
        self.assertFalse(u_pendiente.is_active, 'un nutricionista todavia no aprobado no se toca')
        self.assertEqual(n_sin_venc.proxima_revision_pago, sumar_un_mes(date.today()))
        self.assertIsNone(n_exenta.proxima_revision_pago, 'una cuenta exenta no necesita vencimiento')
        self.assertEqual(n_con_venc.proxima_revision_pago, vencimiento_real, 'no se toca un vencimiento que ya tenia')

        # segunda pasada: no deberia romper ni volver a "reparar" nada
        resp2 = c.post('/mi-panel/nutricionistas/reparar-logins/', follow=True)
        self.assertEqual(resp2.status_code, 200)

    def test_panel_eliminar_nutricionista_borra_todo(self):
        """Antes solo se podia borrar una cuenta de nutricionista desde
        /admin/ — tiene que poder hacerse tambien desde el panel normal,
        para limpiar registros duplicados/de prueba."""
        u = User.objects.create_user(username='para_borrar', email='paraborrar@example.com', password='x')
        nutri = Nutricionista.objects.create(user=u, matricula='MP-BORRAR')
        pk_nutri, pk_user = nutri.pk, u.pk

        c = Client()
        c.force_login(self.owner)
        resp = c.post(f'/mi-panel/nutricionistas/{pk_nutri}/eliminar/', follow=True)
        self.assertEqual(resp.status_code, 200)

        self.assertFalse(Nutricionista.objects.filter(pk=pk_nutri).exists())
        self.assertFalse(User.objects.filter(pk=pk_user).exists())

    def test_paginas_publicas_dinamicas_no_se_cachean(self):
        """El botón "SACAR TURNO" (y en general, si un perfil está o no
        visible) depende de datos que cambian todo el tiempo — sin cabeceras
        explícitas de no-cache, un navegador (Safari es históricamente el más
        agresivo con esto) puede mostrar una versión vieja de la página
        aunque el estado real ya haya cambiado."""
        c = Client()
        paginas = ['/', '/nutricionistas/', f'/nutricionistas/{self.n1.slug}/']
        for url in paginas:
            resp = c.get(url)
            self.assertIn('no-cache', resp.headers.get('Cache-Control', ''), msg=f'{url} sin Cache-Control')

    def test_aprobar_a_mano_carga_vencimiento_de_un_mes(self):
        """Si se aprueba a mano (p.ej. no pudo pagar por el sitio y se activo
        la cuenta a mano) y todavia no tenia ningun vencimiento cargado,
        tiene que quedar con vencimiento a un mes — antes quedaba aprobada
        para siempre sin vencimiento."""
        from .utils import sumar_un_mes

        u = User.objects.create_user(username='aprobar_a_mano', password='x', is_active=False)
        nutri = Nutricionista.objects.create(user=u, matricula='MP-AMANO', aprobado=False)
        self.assertIsNone(nutri.proxima_revision_pago)

        c = Client()
        c.force_login(self.owner)
        c.post(f'/mi-panel/nutricionistas/{nutri.pk}/toggle/')

        nutri.refresh_from_db()
        self.assertTrue(nutri.aprobado)
        self.assertEqual(nutri.proxima_revision_pago, sumar_un_mes(date.today()))

    def test_aprobar_exenta_no_carga_vencimiento(self):
        """Una cuenta marcada como exenta de pago no necesita vencimiento —
        no se le tiene que cargar ninguno al aprobarla."""
        u = User.objects.create_user(username='aprobar_exenta', password='x', is_active=False)
        nutri = Nutricionista.objects.create(user=u, matricula='MP-EXENTA', aprobado=False, exento_de_pago=True)

        c = Client()
        c.force_login(self.owner)
        c.post(f'/mi-panel/nutricionistas/{nutri.pk}/toggle/')

        nutri.refresh_from_db()
        self.assertTrue(nutri.aprobado)
        self.assertIsNone(nutri.proxima_revision_pago)

    def test_reaprobar_no_pisa_un_vencimiento_que_ya_tenia(self):
        """Si ya tenia un vencimiento real cargado (por un pago de verdad) y
        se la da de baja y se la vuelve a aprobar, no se le tiene que regalar
        un mes de mas encima del que ya tenia pagado."""
        u = User.objects.create_user(username='reaprobar_con_pago', password='x')
        vencimiento_real = date.today() + timedelta(days=200)
        nutri = Nutricionista.objects.create(
            user=u, matricula='MP-REAP', aprobado=True, proxima_revision_pago=vencimiento_real,
        )

        c = Client()
        c.force_login(self.owner)
        c.post(f'/mi-panel/nutricionistas/{nutri.pk}/toggle/')  # dar de baja
        c.post(f'/mi-panel/nutricionistas/{nutri.pk}/toggle/')  # re-aprobar

        nutri.refresh_from_db()
        self.assertTrue(nutri.aprobado)
        self.assertEqual(nutri.proxima_revision_pago, vencimiento_real)
