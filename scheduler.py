import threading
import time
import schedule
from datetime import date, timedelta, datetime

import config
from database import get_connection
from notificaciones import enviar_recordatorio
from citas import expirar_citas_pasadas

# Registro de citas ya programadas para evitar duplicados
_recordatorios_programados = set()
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Logica de recordatorio individual
# ─────────────────────────────────────────────────────────────

def _ejecutar_recordatorio(cita_id):
    """
    Busca la cita en la BD y envia el recordatorio al paciente.
    Retorna schedule.CancelJob para que la tarea se elimine
    automaticamente despues de ejecutarse (job de una sola vez).
    """
    with get_connection() as conn:
        cita = conn.execute("""
            SELECT c.id, c.fecha, c.hora, c.motivo, c.estado, c.token,
                   p.nombre, p.correo
            FROM citas c
            JOIN pacientes p ON c.paciente_id = p.id
            WHERE c.id = ?
        """, (cita_id,)).fetchone()

    if not cita:
        print(f"[Scheduler] Cita {cita_id} no encontrada, se omite.")
        return schedule.CancelJob

    if cita["estado"] in ("cancelada", "completada"):
        print(f"[Scheduler] Cita {cita_id} en estado '{cita['estado']}', recordatorio omitido.")
        return schedule.CancelJob

    if not cita["correo"]:
        print(f"[Scheduler] Paciente de cita {cita_id} sin correo, recordatorio omitido.")
        return schedule.CancelJob

    datos_cita = {
        "nombre_paciente": cita["nombre"],
        "fecha":           cita["fecha"],
        "hora":            cita["hora"],
        "motivo":          cita["motivo"],
    }

    enviado = enviar_recordatorio(datos_cita, cita["correo"])
    estado  = "enviado" if enviado else "fallo"
    print(f"[Scheduler] Recordatorio cita {cita_id} -> {cita['correo']} [{estado}]")

    with _lock:
        _recordatorios_programados.discard(cita_id)

    return schedule.CancelJob


# ─────────────────────────────────────────────────────────────
# Programar un recordatorio individual
# ─────────────────────────────────────────────────────────────

def programar_recordatorio(cita_id, hora_envio):
    """
    Registra una tarea diferida en memoria para enviar el recordatorio
    a la hora_envio indicada (formato 'HH:MM').
    Si la cita ya esta programada, no la duplica.
    """
    with _lock:
        if cita_id in _recordatorios_programados:
            return
        _recordatorios_programados.add(cita_id)

    schedule.every().day.at(hora_envio).do(
        _ejecutar_recordatorio, cita_id
    ).tag(f"cita_{cita_id}")

    print(f"[Scheduler] Recordatorio programado: cita {cita_id} a las {hora_envio}")


# ─────────────────────────────────────────────────────────────
# Carga inicial de recordatorios pendientes
# ─────────────────────────────────────────────────────────────

def programar_recordatorio_si_aplica(cita_id, fecha_str, hora_str):
    """
    Programa el recordatorio de una cita solo si la hora de envio
    (1 hora antes) aun no ha pasado. Util al crear una cita nueva.
    """
    fecha_cita    = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
    hora_envio_dt = fecha_cita - timedelta(hours=config.HORAS_RECORDATORIO)

    if hora_envio_dt <= datetime.now():
        print(f"[Scheduler] Recordatorio cita {cita_id} omitido: hora de envio ya paso ({hora_envio_dt}).")
        return

    hora_envio = hora_envio_dt.strftime("%H:%M")
    programar_recordatorio(cita_id, hora_envio)


def cargar_recordatorios_pendientes():
    """
    Al iniciar, consulta las citas de hoy y mañana con estado
    pendiente o confirmada y programa sus recordatorios si aún no pasaron.
    """
    hoy    = date.today().strftime("%Y-%m-%d")
    manana = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        citas = conn.execute("""
            SELECT c.id, c.fecha, c.hora, p.correo
            FROM citas c
            JOIN pacientes p ON c.paciente_id = p.id
            WHERE c.fecha IN (?, ?) AND c.estado IN ('pendiente', 'confirmada')
        """, (hoy, manana)).fetchall()

    if not citas:
        print(f"[Scheduler] Sin citas pendientes para hoy/manana.")
        return

    programados = 0
    for cita in citas:
        if not cita["correo"]:
            continue
        programar_recordatorio_si_aplica(cita["id"], cita["fecha"], cita["hora"])
        programados += 1

    print(f"[Scheduler] {programados} recordatorio(s) evaluados para hoy/manana.")


# ─────────────────────────────────────────────────────────────
# Loop en hilo separado
# ─────────────────────────────────────────────────────────────

def _loop():
    """Ejecuta las tareas pendientes de schedule cada 30 segundos."""
    while True:
        schedule.run_pending()
        time.sleep(30)


def iniciar():
    """
    Arranca el scheduler en un hilo daemon:
    - daemon=True garantiza que el hilo muere cuando el proceso principal termina.
    - Carga los recordatorios del dia siguiente al iniciar.
    - Programa una recarga diaria a las 00:05 para el dia siguiente.
    """
    expirar_citas_pasadas()
    cargar_recordatorios_pendientes()

    # Expirar citas pasadas cada dia a medianoche
    schedule.every().day.at("00:10").do(expirar_citas_pasadas)
    # Recargar recordatorios cada dia a medianoche
    schedule.every().day.at("00:05").do(cargar_recordatorios_pendientes)

    hilo = threading.Thread(target=_loop, name="scheduler", daemon=True)
    hilo.start()
    print("[Scheduler] Hilo iniciado.")


def detener():
    """Limpia todas las tareas programadas."""
    schedule.clear()
    print("[Scheduler] Tareas eliminadas.")
