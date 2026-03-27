from datetime import date, datetime, timedelta
from database import get_connection

# Transiciones de estado permitidas
TRANSICIONES = {
    "pendiente":   {"confirmada", "cancelada", "expirada"},
    "confirmada":  {"completada", "cancelada", "expirada"},
    "completada":  set(),
    "cancelada":   set(),
    "expirada":    set(),
}


# ─────────────────────────────────────────────────────────────
# Utilidades internas de fecha
# ─────────────────────────────────────────────────────────────

def _to_date(fecha_str):
    """Convierte 'YYYY-MM-DD' a objeto date."""
    return datetime.strptime(fecha_str, "%Y-%m-%d").date()


def _to_time(hora_str):
    """Convierte 'HH:MM' a objeto time."""
    return datetime.strptime(hora_str, "%H:%M").time()


def _dia_semana(fecha_str):
    """
    Retorna el dia de semana en convencion de la tabla horarios:
    1=Lunes ... 6=Sabado. Domingo no tiene horario definido.
    """
    return _to_date(fecha_str).isoweekday()  # 1=Lunes, 7=Domingo


# ─────────────────────────────────────────────────────────────
# Corazon del modulo: verificacion de disponibilidad
# ─────────────────────────────────────────────────────────────

def verificar_disponibilidad(fecha, hora):
    """
    Retorna True si el slot (fecha, hora) esta disponible:
      1. La fecha no es en el pasado.
      2. El dia de la semana tiene horario activo que cubra esa hora.
      3. No existe cita pendiente o confirmada en ese mismo slot.
    """
    # 1. Fecha no en el pasado
    if _to_date(fecha) < date.today():
        return False

    hora_dt = _to_time(hora)
    dia = _dia_semana(fecha)

    # 2. Verificar que cae dentro de un bloque de horario disponible
    with get_connection() as conn:
        bloques = conn.execute(
            """SELECT hora_inicio, hora_fin FROM horarios
               WHERE dia_semana = ? AND disponible = 1""",
            (dia,)
        ).fetchall()

        if not bloques:
            return False

        en_horario = any(
            _to_time(b["hora_inicio"]) <= hora_dt < _to_time(b["hora_fin"])
            for b in bloques
        )
        if not en_horario:
            return False

        # 3. Sin colision con citas existentes
        colision = conn.execute(
            """SELECT COUNT(*) FROM citas
               WHERE fecha = ? AND hora = ? AND estado IN ('pendiente', 'confirmada')""",
            (fecha, hora)
        ).fetchone()[0]

    return colision == 0


# ─────────────────────────────────────────────────────────────
# CRUD de citas
# ─────────────────────────────────────────────────────────────

def crear_cita(paciente_id, fecha, hora, motivo=None):
    """
    Inserta una nueva cita si el slot esta disponible.
    Retorna el id generado o lanza ValueError si no hay disponibilidad.
    """
    if not verificar_disponibilidad(fecha, hora):
        raise ValueError(f"El slot {fecha} {hora} no esta disponible.")

    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO citas (paciente_id, fecha, hora, motivo) VALUES (?, ?, ?, ?)",
            (paciente_id, fecha, hora, motivo)
        )
        return cursor.lastrowid


def obtener_citas_del_dia(fecha):
    """Retorna todas las citas de una fecha ordenadas por hora."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT c.*, p.nombre, p.correo, p.telefono
               FROM citas c
               JOIN pacientes p ON c.paciente_id = p.id
               WHERE c.fecha = ?
               ORDER BY c.hora""",
            (fecha,)
        ).fetchall()


def obtener_citas_semana(fecha_inicio):
    """Retorna las citas de los 7 dias siguientes a fecha_inicio."""
    fecha_fin = (_to_date(fecha_inicio) + timedelta(days=6)).strftime("%Y-%m-%d")

    with get_connection() as conn:
        return conn.execute(
            """SELECT c.*, p.nombre, p.correo, p.telefono
               FROM citas c
               JOIN pacientes p ON c.paciente_id = p.id
               WHERE c.fecha BETWEEN ? AND ?
               ORDER BY c.fecha, c.hora""",
            (fecha_inicio, fecha_fin)
        ).fetchall()


def cambiar_estado(cita_id, nuevo_estado):
    """
    Actualiza el estado de una cita validando que la transicion sea permitida.
    Lanza ValueError si la transicion no es valida.
    """
    with get_connection() as conn:
        cita = conn.execute(
            "SELECT estado FROM citas WHERE id = ?", (cita_id,)
        ).fetchone()

        if not cita:
            raise ValueError(f"No existe la cita con id={cita_id}.")

        estado_actual = cita["estado"]
        if nuevo_estado not in TRANSICIONES[estado_actual]:
            raise ValueError(
                f"Transicion no permitida: '{estado_actual}' -> '{nuevo_estado}'."
            )

        conn.execute(
            "UPDATE citas SET estado = ? WHERE id = ?",
            (nuevo_estado, cita_id)
        )


def cancelar_cita(cita_id):
    """Cancela una cita y libera el slot."""
    cambiar_estado(cita_id, "cancelada")


def expirar_citas_pasadas():
    """
    Marca como 'expirada' todas las citas pendientes o confirmadas
    cuya fecha ya pasó. Retorna el número de citas expiradas.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE citas SET estado = 'expirada'
               WHERE estado IN ('pendiente', 'confirmada')
               AND fecha < date('now')"""
        )
        n = cursor.rowcount
    if n:
        print(f"[Citas] {n} cita(s) marcadas como expiradas.")
    return n


# ─────────────────────────────────────────────────────────────
# Slots disponibles para una fecha (util para el calendario)
# ─────────────────────────────────────────────────────────────

def slots_disponibles(fecha):
    """
    Genera todos los slots de tiempo de una fecha segun los horarios
    configurados y descarta los que ya tienen cita pendiente o confirmada.
    Retorna lista de strings 'HH:MM'.
    """
    dia = _dia_semana(fecha)

    with get_connection() as conn:
        bloques = conn.execute(
            """SELECT hora_inicio, hora_fin, duracion_min FROM horarios
               WHERE dia_semana = ? AND disponible = 1""",
            (dia,)
        ).fetchall()

        ocupados = {
            row["hora"] for row in conn.execute(
                """SELECT hora FROM citas
                   WHERE fecha = ? AND estado IN ('pendiente', 'confirmada')""",
                (fecha,)
            ).fetchall()
        }

    slots = []
    for bloque in bloques:
        inicio = datetime.strptime(bloque["hora_inicio"], "%H:%M")
        fin    = datetime.strptime(bloque["hora_fin"],    "%H:%M")
        delta  = timedelta(minutes=bloque["duracion_min"])

        actual = inicio
        while actual < fin:
            hora_str = actual.strftime("%H:%M")
            if hora_str not in ocupados:
                slots.append(hora_str)
            actual += delta

    return slots
