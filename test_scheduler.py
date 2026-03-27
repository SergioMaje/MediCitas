import time
import schedule
from datetime import date, timedelta
import os

from database import init_db, get_connection
from pacientes import crear_paciente
from citas import crear_cita

# Base de datos limpia
if os.path.exists("medicitas.db"):
    os.remove("medicitas.db")
init_db()

from scheduler import (
    programar_recordatorio,
    cargar_recordatorios_pendientes,
    _recordatorios_programados,
    iniciar,
    detener,
)

def separador(titulo):
    print(f"\n{'-'*45}")
    print(f"  {titulo}")
    print(f"{'-'*45}")

def ok(msg):   print(f"  [OK]    {msg}")
def info(msg): print(f"  [INFO]  {msg}")
def falla(msg): print(f"  [FALLA] {msg}")

MANANA = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")


# ─────────────────────────────────────────
# 1. Preparar datos de prueba
# ─────────────────────────────────────────
separador("1. Preparar datos de prueba")

id_p1 = crear_paciente("Laura Torres", "3001234567", "laura@example.com")
id_p2 = crear_paciente("Juan Mesa",    "3009876543", "juan@example.com")
id_p3 = crear_paciente("Sin Correo",   "3000000000", None)  # sin correo

id_c1 = crear_cita(id_p1, MANANA, "09:00", "Consulta general")
id_c2 = crear_cita(id_p2, MANANA, "10:00", "Control")
id_c3 = crear_cita(id_p3, MANANA, "11:00", "Revision")

ok(f"Pacientes creados: {id_p1}, {id_p2}, {id_p3}")
ok(f"Citas para manana ({MANANA}): {id_c1}, {id_c2}, {id_c3}")


# ─────────────────────────────────────────
# 2. programar_recordatorio individual
# ─────────────────────────────────────────
separador("2. programar_recordatorio")

schedule.clear()
_recordatorios_programados.clear()

programar_recordatorio(id_c1, "08:00")
ok(f"Cita {id_c1} programada")
(ok if id_c1 in _recordatorios_programados else falla)(
    f"Cita {id_c1} en registro de programados"
)

# Intentar duplicado
programar_recordatorio(id_c1, "08:00")
total_jobs = len([j for j in schedule.jobs if f"cita_{id_c1}" in j.tags])
(ok if total_jobs == 1 else falla)(
    f"Sin duplicados: {total_jobs} job(s) para cita {id_c1}  (esperado: 1)"
)


# ─────────────────────────────────────────
# 3. cargar_recordatorios_pendientes
# ─────────────────────────────────────────
separador("3. cargar_recordatorios_pendientes")

schedule.clear()
_recordatorios_programados.clear()

cargar_recordatorios_pendientes()

total_jobs = len([j for j in schedule.jobs if j.tags])
# c3 no tiene correo, no debe programarse
(ok if id_c1 in _recordatorios_programados else falla)(
    f"Cita {id_c1} (con correo) programada"
)
(ok if id_c2 in _recordatorios_programados else falla)(
    f"Cita {id_c2} (con correo) programada"
)
(ok if id_c3 not in _recordatorios_programados else falla)(
    f"Cita {id_c3} (sin correo) omitida correctamente"
)
ok(f"Total jobs en schedule: {total_jobs}")


# ─────────────────────────────────────────
# 4. Hilo daemon
# ─────────────────────────────────────────
separador("4. Hilo daemon")

import threading
schedule.clear()
_recordatorios_programados.clear()

iniciar()
time.sleep(1)  # dar tiempo al hilo a arrancar

hilo = next((t for t in threading.enumerate() if t.name == "scheduler"), None)
(ok if hilo is not None else falla)(
    f"Hilo 'scheduler' activo: {hilo is not None}"
)
(ok if hilo.daemon else falla)(
    f"Hilo es daemon (muere con el proceso principal): {hilo.daemon}"
)


# ─────────────────────────────────────────
# 5. detener
# ─────────────────────────────────────────
separador("5. detener scheduler")

detener()
(ok if len(schedule.jobs) == 0 else falla)(
    f"Jobs eliminados tras detener: {len(schedule.jobs)}  (esperado: 0)"
)


separador("Pruebas completadas")
