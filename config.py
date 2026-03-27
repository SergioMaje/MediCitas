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
