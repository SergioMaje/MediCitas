"""
Prueba la construccion de los mensajes sin necesidad de credenciales reales.
Para probar el envio real, configura .env con tus datos de Gmail y
cambia PROBAR_ENVIO_REAL = True.
"""
from notificaciones import (
    _construir_confirmacion,
    _construir_alerta_medico,
    _construir_recordatorio,
    enviar_confirmacion,
    enviar_alerta_medico,
    enviar_recordatorio,
)

PROBAR_ENVIO_REAL = False  # Cambia a True cuando tengas credenciales en .env

def separador(titulo):
    print(f"\n{'-'*45}")
    print(f"  {titulo}")
    print(f"{'-'*45}")

def ok(msg):   print(f"  [OK]    {msg}")
def info(msg): print(f"  [INFO]  {msg}")


# Datos de prueba reutilizables
DATOS_CITA = {
    "nombre_paciente": "Laura Torres",
    "fecha":  "2026-04-01",
    "hora":   "09:00",
    "motivo": "Consulta general",
    "estado": "pendiente",
}
DATOS_PACIENTE = {
    "nombre":   "Laura Torres",
    "telefono": "3001234567",
    "correo":   "laura@example.com",
}
CORREO_PACIENTE = "laura@example.com"


# ─────────────────────────────────────────
# 1. Construccion del correo de confirmacion
# ─────────────────────────────────────────
separador("1. Construccion: confirmacion al paciente")

msg = _construir_confirmacion(DATOS_CITA, CORREO_PACIENTE)
ok(f"Destinatario : {msg['To']}")
ok(f"Asunto       : {msg['Subject']}")
cuerpo = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
ok("Contiene nombre paciente" if "Laura Torres"  in cuerpo else "FALTA nombre paciente")
ok("Contiene fecha"           if "2026-04-01"    in cuerpo else "FALTA fecha")
ok("Contiene hora"            if "09:00"         in cuerpo else "FALTA hora")
ok("Contiene motivo"          if "Consulta"      in cuerpo else "FALTA motivo")
ok("Contiene telefono clinica" if "Medicitas"    in cuerpo else "FALTA nombre clinica")


# ─────────────────────────────────────────
# 2. Construccion de la alerta al medico
# ─────────────────────────────────────────
separador("2. Construccion: alerta interna al medico")

msg = _construir_alerta_medico(DATOS_CITA, DATOS_PACIENTE)
ok(f"Destinatario : {msg['To']}")
ok(f"Asunto       : {msg['Subject']}")
cuerpo = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
ok("Contiene nombre paciente" if "Laura Torres"  in cuerpo else "FALTA nombre paciente")
ok("Contiene telefono"        if "3001234567"    in cuerpo else "FALTA telefono")
ok("Contiene correo paciente" if "laura@example" in cuerpo else "FALTA correo paciente")
ok("Contiene fecha"           if "2026-04-01"    in cuerpo else "FALTA fecha")
ok("Contiene motivo"          if "Consulta"      in cuerpo else "FALTA motivo")


# ─────────────────────────────────────────
# 3. Construccion del recordatorio
# ─────────────────────────────────────────
separador("3. Construccion: recordatorio al paciente")

msg = _construir_recordatorio(DATOS_CITA, CORREO_PACIENTE)
ok(f"Destinatario : {msg['To']}")
ok(f"Asunto       : {msg['Subject']}")
cuerpo = msg.get_payload(0).get_payload(decode=True).decode("utf-8")
ok("Contiene MANANA"          if "MANANA"        in cuerpo else "FALTA aviso de manana")
ok("Contiene nombre paciente" if "Laura Torres"  in cuerpo else "FALTA nombre paciente")
ok("Contiene fecha"           if "2026-04-01"    in cuerpo else "FALTA fecha")
ok("Contiene hora"            if "09:00"         in cuerpo else "FALTA hora")


# ─────────────────────────────────────────
# 4. Envio real (solo si esta habilitado)
# ─────────────────────────────────────────
separador("4. Envio real via SMTP")

if PROBAR_ENVIO_REAL:
    resultado = enviar_confirmacion(DATOS_CITA, CORREO_PACIENTE)
    ok(f"Confirmacion enviada: {resultado}")

    resultado = enviar_alerta_medico(DATOS_CITA, DATOS_PACIENTE)
    ok(f"Alerta medico enviada: {resultado}")

    resultado = enviar_recordatorio(DATOS_CITA, CORREO_PACIENTE)
    ok(f"Recordatorio enviado: {resultado}")
else:
    info("Envio real desactivado.")
    info("Para probarlo: configura .env y pon PROBAR_ENVIO_REAL = True")


separador("Pruebas completadas")
