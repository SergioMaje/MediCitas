"""
test_flujo_emails.py
====================
Integration tests: verifica que las rutas HTTP disparen los correos correctos.
Usa unittest.mock.patch sobre smtplib.SMTP_SSL para no enviar correos reales.
"""
import os
import unittest
from unittest.mock import patch
from datetime import date, timedelta

# Redirigir la BD a un archivo temporal ANTES de importar cualquier módulo del proyecto
TEST_DB = "test_medicitas.db"
os.environ["DATABASE_PATH"] = TEST_DB

import config
config.DATABASE_PATH = TEST_DB

import schedule
from database import init_db, get_connection
from scheduler import (
    _ejecutar_recordatorio,
    cargar_recordatorios_pendientes,
    programar_recordatorio,
    _recordatorios_programados,
)
import pacientes as pac
import citas as cit
from app import app


# ─────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────

def _proximo_dia_laborable():
    """Devuelve el próximo día laboral (lun–vie) a partir de mañana."""
    hoy = date.today()
    for i in range(1, 15):
        d = hoy + timedelta(days=i)
        if d.weekday() < 5:
            return d.strftime("%Y-%m-%d")
    return None


def _resetear_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()


# ─────────────────────────────────────────────────────────────
# Clase 1: Flujo de agendamiento público
# ─────────────────────────────────────────────────────────────

class TestBookingFlowEmails(unittest.TestCase):

    def setUp(self):
        _resetear_db()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.dia = _proximo_dia_laborable()

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def _inyectar_sesion(self, paciente_id, nombre, correo):
        with self.client.session_transaction() as sess:
            sess["paciente_id"]     = paciente_id
            sess["paciente_nombre"] = nombre
            sess["paciente_correo"] = correo

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_does_not_send_email_to_patient(self, mock_smtp_class):
        pid = pac.crear_paciente("Laura Torres", "3001234567", "laura@example.com")
        self._inyectar_sesion(pid, "Laura Torres", "laura@example.com")

        resp = self.client.post("/agendar/cita",
                                data={"fecha": self.dia, "hora": "09:00", "motivo": ""})

        self.assertEqual(resp.status_code, 302)
        smtp_inst = mock_smtp_class.return_value.__enter__.return_value
        destinatarios = [c.args[1] for c in smtp_inst.sendmail.call_args_list]
        self.assertNotIn("laura@example.com", destinatarios)
        self.assertEqual(smtp_inst.sendmail.call_count, 1)

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_sends_alerta_medico_email(self, mock_smtp_class):
        pid = pac.crear_paciente("Laura Torres", "3001234567", "laura@example.com")
        self._inyectar_sesion(pid, "Laura Torres", "laura@example.com")

        self.client.post("/agendar/cita",
                         data={"fecha": self.dia, "hora": "09:00", "motivo": ""})

        smtp_inst = mock_smtp_class.return_value.__enter__.return_value
        destinatarios = [c.args[1] for c in smtp_inst.sendmail.call_args_list]
        self.assertIn(config.EMAIL_DOCTOR, destinatarios)

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_no_confirmacion_when_no_correo(self, mock_smtp_class):
        pid = pac.crear_paciente("Sin Correo", "3001234567", None)
        self._inyectar_sesion(pid, "Sin Correo", "")

        self.client.post("/agendar/cita",
                         data={"fecha": self.dia, "hora": "09:00", "motivo": ""})

        smtp_inst = mock_smtp_class.return_value.__enter__.return_value
        self.assertEqual(smtp_inst.sendmail.call_count, 1)
        destinatario = smtp_inst.sendmail.call_args.args[1]
        self.assertEqual(destinatario, config.EMAIL_DOCTOR)

    def test_booking_step2_requires_step1_session(self):
        resp = self.client.get("/agendar/cita")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/agendar", resp.headers["Location"])

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_invalid_hora_malformed(self, mock_smtp_class):
        pid = pac.crear_paciente("Test", "3001234567", "test@example.com")
        self._inyectar_sesion(pid, "Test", "test@example.com")

        resp = self.client.post("/agendar/cita",
                                data={"fecha": self.dia, "hora": "25:99", "motivo": ""})

        self.assertEqual(resp.status_code, 200)
        mock_smtp_class.assert_not_called()

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_second_cita_same_day_rejected(self, mock_smtp_class):
        pid = pac.crear_paciente("Laura Torres", "3001234567", "laura@example.com")
        cit.crear_cita(pid, self.dia, "09:00", "Primera cita")
        self._inyectar_sesion(pid, "Laura Torres", "laura@example.com")

        resp = self.client.post("/agendar/cita",
                                data={"fecha": self.dia, "hora": "10:00", "motivo": ""})

        self.assertEqual(resp.status_code, 200)
        mock_smtp_class.assert_not_called()

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_booking_hora_not_in_schedule_bypassing_ajax(self, mock_smtp_class):
        pid = pac.crear_paciente("Test", "3001234567", "test@example.com")
        self._inyectar_sesion(pid, "Test", "test@example.com")

        # 14:30 cae en la pausa entre bloques (13:00–15:00)
        resp = self.client.post("/agendar/cita",
                                data={"fecha": self.dia, "hora": "14:30", "motivo": ""})

        self.assertEqual(resp.status_code, 200)
        mock_smtp_class.assert_not_called()


# ─────────────────────────────────────────────────────────────
# Clase 2: Bloqueo de fecha (panel médico)
# ─────────────────────────────────────────────────────────────

class TestBlockingFlowEmails(unittest.TestCase):

    def setUp(self):
        _resetear_db()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.dia = _proximo_dia_laborable()
        # Login como médico
        self.client.post("/login", data={
            "usuario":  config.DOCTOR_USUARIO,
            "password": config.DOCTOR_PASSWORD,
        })

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_blocking_sends_cancellation_emails_to_all_patients(self, mock_smtp_class):
        p1 = pac.crear_paciente("Ana Garcia",  "3001", "ana@example.com")
        p2 = pac.crear_paciente("Luis Ruiz",   "3002", "luis@example.com")
        cit.crear_cita(p1, self.dia, "09:00", "Control")
        cit.crear_cita(p2, self.dia, "10:00", "Consulta")

        self.client.post("/panel/horarios", data={
            "accion": "bloquear", "fecha": self.dia, "notificar": "1"
        })

        smtp_inst = mock_smtp_class.return_value.__enter__.return_value
        destinatarios = {c.args[1] for c in smtp_inst.sendmail.call_args_list}
        self.assertIn("ana@example.com",  destinatarios)
        self.assertIn("luis@example.com", destinatarios)

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_blocking_no_emails_when_notificar_off(self, mock_smtp_class):
        p1 = pac.crear_paciente("Ana Garcia", "3001", "ana@example.com")
        cit.crear_cita(p1, self.dia, "09:00", "Control")

        self.client.post("/panel/horarios", data={
            "accion": "bloquear", "fecha": self.dia
        })

        mock_smtp_class.assert_not_called()

    @patch("notificaciones.smtplib.SMTP_SSL")
    def test_blocking_skips_patients_without_correo(self, mock_smtp_class):
        p1 = pac.crear_paciente("Con Correo",  "3001", "con@example.com")
        p2 = pac.crear_paciente("Sin Correo",  "3002", None)
        cit.crear_cita(p1, self.dia, "09:00", "Control")
        cit.crear_cita(p2, self.dia, "10:00", "Consulta")

        self.client.post("/panel/horarios", data={
            "accion": "bloquear", "fecha": self.dia, "notificar": "1"
        })

        smtp_inst = mock_smtp_class.return_value.__enter__.return_value
        self.assertEqual(smtp_inst.sendmail.call_count, 1)
        self.assertEqual(smtp_inst.sendmail.call_args.args[1], "con@example.com")

    def test_blocking_past_date_rejected(self):
        self.client.post("/panel/horarios", data={
            "accion": "bloquear", "fecha": "2020-01-01"
        })

        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM dias_bloqueados WHERE fecha = '2020-01-01'"
            ).fetchone()[0]
        self.assertEqual(count, 0)


# ─────────────────────────────────────────────────────────────
# Clase 3: Recordatorios del scheduler
# ─────────────────────────────────────────────────────────────

class TestSchedulerReminderEmails(unittest.TestCase):

    def setUp(self):
        _resetear_db()
        schedule.clear()
        _recordatorios_programados.clear()
        self.manana = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    def tearDown(self):
        schedule.clear()
        _recordatorios_programados.clear()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch("scheduler.enviar_recordatorio")
    def test_ejecutar_recordatorio_sends_email(self, mock_enviar):
        pid     = pac.crear_paciente("Laura Torres", "3001234567", "laura@example.com")
        cita_id = cit.crear_cita(pid, self.manana, "09:00", "Consulta")

        result = _ejecutar_recordatorio(cita_id)

        mock_enviar.assert_called_once()
        datos, correo = mock_enviar.call_args.args
        self.assertEqual(datos["nombre_paciente"], "Laura Torres")
        self.assertEqual(datos["fecha"], self.manana)
        self.assertEqual(datos["hora"],  "09:00")
        self.assertEqual(correo, "laura@example.com")
        self.assertIs(result, schedule.CancelJob)

    @patch("scheduler.enviar_recordatorio")
    def test_ejecutar_recordatorio_skips_cancelled(self, mock_enviar):
        pid     = pac.crear_paciente("Test", "3001", "test@example.com")
        cita_id = cit.crear_cita(pid, self.manana, "09:00", None)
        cit.cancelar_cita(cita_id)

        _ejecutar_recordatorio(cita_id)

        mock_enviar.assert_not_called()

    @patch("scheduler.enviar_recordatorio")
    def test_ejecutar_recordatorio_skips_no_correo(self, mock_enviar):
        pid     = pac.crear_paciente("Sin Correo", "3001", None)
        cita_id = cit.crear_cita(pid, self.manana, "09:00", None)

        _ejecutar_recordatorio(cita_id)

        mock_enviar.assert_not_called()

    @patch("scheduler.enviar_recordatorio")
    def test_ejecutar_recordatorio_missing_cita(self, mock_enviar):
        result = _ejecutar_recordatorio(99999)

        mock_enviar.assert_not_called()
        self.assertIs(result, schedule.CancelJob)

    @patch("scheduler.programar_recordatorio")
    def test_cargar_recordatorios_only_programs_patients_with_correo(self, mock_programar):
        p1 = pac.crear_paciente("Con Correo", "3001", "a@example.com")
        p2 = pac.crear_paciente("Sin Correo", "3002", None)
        cit.crear_cita(p1, self.manana, "09:00", None)
        cit.crear_cita(p2, self.manana, "10:00", None)

        cargar_recordatorios_pendientes()

        self.assertEqual(mock_programar.call_count, 1)

    @patch("scheduler.programar_recordatorio")
    def test_recordatorio_programado_1h_antes(self, mock_programar):
        pid = pac.crear_paciente("Laura Torres", "3001", "laura@example.com")
        cit.crear_cita(pid, self.manana, "10:00", None)

        cargar_recordatorios_pendientes()

        _, hora_envio = mock_programar.call_args.args
        self.assertEqual(hora_envio, "09:00")  # 10:00 - 1h = 09:00

    @patch("scheduler.enviar_recordatorio")
    def test_recordatorio_es_solo_informativo(self, mock_enviar):
        pid     = pac.crear_paciente("Laura Torres", "3001", "laura@example.com")
        cita_id = cit.crear_cita(pid, self.manana, "09:00", "Consulta")

        _ejecutar_recordatorio(cita_id)

        mock_enviar.assert_called_once()
        self.assertEqual(mock_enviar.call_args.args[1], "laura@example.com")


# ─────────────────────────────────────────────────────────────
# Clase 4: Confirmación de asistencia del paciente
# ─────────────────────────────────────────────────────────────

class TestConfirmacionAsistencia(unittest.TestCase):

    def setUp(self):
        _resetear_db()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.dia = _proximo_dia_laborable()
        pid = pac.crear_paciente("Laura Torres", "3001", "laura@example.com")
        self.cita_id = cit.crear_cita(pid, self.dia, "09:00", "Consulta")
        self.token   = cit.obtener_token(self.cita_id)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def _get_confirmo(self):
        with get_connection() as conn:
            return conn.execute(
                "SELECT paciente_confirmo FROM citas WHERE id = ?", (self.cita_id,)
            ).fetchone()[0]

    def test_confirmar_asistencia_si(self):
        resp = self.client.get(f"/confirmar/{self.token}?r=si")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._get_confirmo(), 1)

    def test_confirmar_asistencia_no(self):
        resp = self.client.get(f"/confirmar/{self.token}?r=no")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._get_confirmo(), -1)

    def test_confirmar_token_invalido(self):
        resp = self.client.get("/confirmar/token-que-no-existe")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'data-estado="invalido"', resp.data)

    def test_confirmar_idempotente(self):
        self.client.get(f"/confirmar/{self.token}?r=si")
        resp = self.client.get(f"/confirmar/{self.token}?r=si")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'data-estado="ya_respondida"', resp.data)
        self.assertEqual(self._get_confirmo(), 1)

    def test_confirmar_cita_cancelada(self):
        cit.cancelar_cita(self.cita_id)
        resp = self.client.get(f"/confirmar/{self.token}?r=si")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'data-estado="no_activa"', resp.data)
        self.assertEqual(self._get_confirmo(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
