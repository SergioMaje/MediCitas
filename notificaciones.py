import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_DOCTOR,
    CLINICA_NOMBRE, CLINICA_TELEFONO
)


# ─────────────────────────────────────────────────────────────
# Construccion de mensajes
# ─────────────────────────────────────────────────────────────

def _construir_confirmacion(datos_cita, correo_paciente):
    """Correo enviado al paciente al crear la cita. Informa que está pendiente de revisión."""
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = correo_paciente
    msg["Subject"] = f"Solicitud de cita recibida - {CLINICA_NOMBRE}"

    cuerpo = f"""
Estimado/a {datos_cita['nombre_paciente']},

Hemos recibido su solicitud de cita. Esta pendiente de revision por el medico.

  Fecha:   {datos_cita['fecha']}
  Hora:    {datos_cita['hora']}
  Motivo:  {datos_cita.get('motivo') or 'Consulta medica'}

Le enviaremos un segundo correo cuando el medico confirme su cita.

Si necesita cancelar o tiene alguna duda, contactenos:
  Telefono: {CLINICA_TELEFONO}
  Correo:   {EMAIL_SENDER}

Saludos,
{CLINICA_NOMBRE}
"""
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    return msg


def _construir_alerta_medico(datos_cita, datos_paciente):
    """Alerta interna dirigida al medico con el perfil del paciente."""
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_DOCTOR
    msg["Subject"] = f"[Nueva cita] {datos_paciente['nombre']} - {datos_cita['fecha']} {datos_cita['hora']}"

    cuerpo = f"""
NUEVA CITA AGENDADA
{'='*40}

DATOS DEL PACIENTE
  Nombre:   {datos_paciente['nombre']}
  Telefono: {datos_paciente.get('telefono') or 'No registrado'}
  Correo:   {datos_paciente.get('correo') or 'No registrado'}

DETALLES DE LA CITA
  Fecha:    {datos_cita['fecha']}
  Hora:     {datos_cita['hora']}
  Motivo:   {datos_cita.get('motivo') or 'No especificado'}
  Estado:   {datos_cita.get('estado', 'pendiente')}

{'='*40}
{CLINICA_NOMBRE} - Sistema automatico
"""
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    return msg


def _construir_recordatorio(datos_cita, correo_paciente):
    """Recordatorio informativo 1 hora antes de la cita."""
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = correo_paciente
    msg["Subject"] = f"Recordatorio: su cita es en 1 hora - {CLINICA_NOMBRE}"

    cuerpo = f"""
Estimado/a {datos_cita['nombre_paciente']},

Le recordamos que tiene una cita en 1 HORA.

  Fecha:    {datos_cita['fecha']}
  Hora:     {datos_cita['hora']}
  Motivo:   {datos_cita.get('motivo') or 'Consulta medica'}

Si necesita cancelar, contactenos con anticipacion:
  Telefono: {CLINICA_TELEFONO}
  Correo:   {EMAIL_SENDER}

Saludos,
{CLINICA_NOMBRE}
"""
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    return msg


# ─────────────────────────────────────────────────────────────
# Envio seguro via SMTP_SSL
# ─────────────────────────────────────────────────────────────

def _enviar(msg):
    """
    Envia el mensaje usando SMTP_SSL (puerto 465).
    Retorna True si el envio fue exitoso, False si hubo error.
    """
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_SENDER, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_SENDER, msg["To"], msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print("Error: credenciales de correo invalidas. Verifica EMAIL_SENDER y EMAIL_PASSWORD en .env")
        return False
    except smtplib.SMTPException as e:
        print(f"Error SMTP al enviar a {msg['To']}: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado al enviar correo: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# API publica del modulo
# ─────────────────────────────────────────────────────────────

def enviar_confirmacion(datos_cita, correo_paciente):
    """
    Envia el correo de confirmacion al paciente al instante.

    datos_cita debe contener: nombre_paciente, fecha, hora, motivo (opcional).
    """
    msg = _construir_confirmacion(datos_cita, correo_paciente)
    return _enviar(msg)


def enviar_alerta_medico(datos_cita, datos_paciente):
    """
    Envia la alerta interna al medico al instante.

    datos_paciente debe contener: nombre, telefono (opcional), correo (opcional).
    datos_cita debe contener: fecha, hora, motivo (opcional), estado (opcional).
    """
    msg = _construir_alerta_medico(datos_cita, datos_paciente)
    return _enviar(msg)


def enviar_recordatorio(datos_cita, correo_paciente):
    """
    Envia el recordatorio informativo al paciente 1 hora antes de la cita.

    datos_cita debe contener: nombre_paciente, fecha, hora, motivo (opcional).
    """
    msg = _construir_recordatorio(datos_cita, correo_paciente)
    return _enviar(msg)


def enviar_confirmacion_medico(datos_cita, correo_paciente):
    """
    Notifica al paciente que el médico confirmó su cita.

    datos_cita debe contener: nombre_paciente, fecha, hora, motivo (opcional).
    """
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = correo_paciente
    msg["Subject"] = f"Tu cita fue confirmada - {CLINICA_NOMBRE}"

    cuerpo = f"""
Estimado/a {datos_cita['nombre_paciente']},

Su cita ha sido confirmada por el médico.

  Fecha:   {datos_cita['fecha']}
  Hora:    {datos_cita['hora']}
  Motivo:  {datos_cita.get('motivo') or 'Consulta medica'}

Por favor llegue 10 minutos antes de su cita.

Si necesita cancelar o reprogramar, contactenos:
  Telefono: {CLINICA_TELEFONO}
  Correo:   {EMAIL_SENDER}

Saludos,
{CLINICA_NOMBRE}
"""
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    return _enviar(msg)


def enviar_cancelacion_por_bloqueo(datos_cita, correo_paciente):
    """
    Notifica al paciente que su cita fue cancelada porque el médico
    no estará disponible ese día, e invita a reprogramar.

    datos_cita debe contener: nombre_paciente, fecha, hora, motivo (opcional).
    """
    msg = MIMEMultipart()
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = correo_paciente
    msg["Subject"] = f"Cita cancelada - {CLINICA_NOMBRE}"

    cuerpo = f"""
Estimado/a {datos_cita['nombre_paciente']},

Le informamos que su cita ha sido cancelada debido a que el medico
no estara disponible en la fecha indicada.

  Fecha cancelada: {datos_cita['fecha']}
  Hora cancelada:  {datos_cita['hora']}
  Motivo original: {datos_cita.get('motivo') or 'Consulta medica'}

Para reprogramar su cita, por favor contactenos:
  Telefono: {CLINICA_TELEFONO}
  Correo:   {EMAIL_SENDER}

Lamentamos los inconvenientes causados.

Saludos,
{CLINICA_NOMBRE}
"""
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
    return _enviar(msg)
