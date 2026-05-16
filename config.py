import os
from dotenv import load_dotenv

load_dotenv()

# Credenciales de correo
EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_DOCTOR   = os.getenv("EMAIL_DOCTOR", "")

# Datos de la clinica
CLINICA_NOMBRE   = os.getenv("CLINICA_NOMBRE", "Medicitas")
CLINICA_TELEFONO = os.getenv("CLINICA_TELEFONO", "")

# Base de datos
DATABASE_PATH = os.getenv("DATABASE_PATH", "medicitas.db")

# Flask
SECRET_KEY      = os.getenv("SECRET_KEY", "dev_key_insegura")
DOCTOR_USUARIO  = os.getenv("DOCTOR_USUARIO", "admin")
DOCTOR_PASSWORD = os.getenv("DOCTOR_PASSWORD", "admin123")
APP_URL         = os.getenv("APP_URL", "http://localhost:5000")

# Reglas de agendamiento
DIAS_MAX_ANTICIPACION  = int(os.getenv("DIAS_MAX_ANTICIPACION", "60"))   # máximo días hacia el futuro
HORAS_MIN_ANTICIPACION = int(os.getenv("HORAS_MIN_ANTICIPACION", "1"))   # mínimo horas antes del slot
HORAS_RECORDATORIO     = int(os.getenv("HORAS_RECORDATORIO", "1"))        # horas antes de la cita para enviar el recordatorio
