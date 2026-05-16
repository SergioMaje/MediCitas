import uuid
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
      1. La fecha no es en el pasado y no supera el límite de anticipación.
      2. Para hoy: la hora no ha pasado (más margen mínimo de anticipación).
      3. El dia de la semana tiene horario activo que cubra esa hora.
      4. No existe cita pendiente o confirmada en ese mismo slot.
    """
    import config
    fecha_dt = _to_date(fecha)
    hoy      = date.today()

    if fecha_dt < hoy:
        return False

    if fecha_dt > hoy + timedelta(days=config.DIAS_MAX_ANTICIPACION):
        return False

    # Para hoy, descartar slots que ya pasaron (+ margen mínimo)
    if fecha_dt == hoy:
        cutoff = (datetime.now() + timedelta(hours=config.HORAS_MIN_ANTICIPACION)).time()
        if _to_time(hora) < cutoff:
            return False

    hora_dt = _to_time(hora)
    dia = _dia_semana(fecha)

    with get_connection() as conn:
        # 1b. Verificar que la fecha no está bloqueada por el médico
        if conn.execute(
            "SELECT 1 FROM dias_bloqueados WHERE fecha = ?", (fecha,)
        ).fetchone():
            return False

        # 2. Verificar que cae dentro de un bloque de horario disponible
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
        ya_tiene = conn.execute("""
            SELECT 1 FROM citas
            WHERE paciente_id = ? AND fecha = ? AND estado IN ('pendiente', 'confirmada')
        """, (paciente_id, fecha)).fetchone()

        if ya_tiene:
            raise ValueError("Ya tienes una cita agendada para ese día. Solo se permite una cita por día.")

        token = str(uuid.uuid4())
        cursor = conn.execute(
            "INSERT INTO citas (paciente_id, fecha, hora, motivo, token) VALUES (?, ?, ?, ?, ?)",
            (paciente_id, fecha, hora, motivo, token)
        )
        return cursor.lastrowid


def obtener_token(cita_id):
    """Retorna el token de confirmación de una cita."""
    with get_connection() as conn:
        row = conn.execute("SELECT token FROM citas WHERE id = ?", (cita_id,)).fetchone()
        return row["token"] if row else None


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
        if estado_actual == nuevo_estado:
            return
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
    Para hoy, también descarta slots que ya pasaron (+ margen mínimo de config).
    Retorna lista de strings 'HH:MM'. Retorna [] si la fecha está bloqueada.
    """
    import config

    fecha_dt = _to_date(fecha)
    hoy      = date.today()

    if fecha_dt < hoy or fecha_dt > hoy + timedelta(days=config.DIAS_MAX_ANTICIPACION):
        return []

    # Hora de corte para hoy: ahora + margen mínimo de anticipación
    cutoff_str = None
    if fecha_dt == hoy:
        cutoff = datetime.now() + timedelta(hours=config.HORAS_MIN_ANTICIPACION)
        cutoff_str = cutoff.strftime("%H:%M")

    dia = _dia_semana(fecha)

    with get_connection() as conn:
        if conn.execute(
            "SELECT 1 FROM dias_bloqueados WHERE fecha = ?", (fecha,)
        ).fetchone():
            return []

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
                if cutoff_str is None or hora_str >= cutoff_str:
                    slots.append(hora_str)
            actual += delta

    return slots


def citas_proxima_fecha(hoy_str):
    """
    Retorna (lista_citas, fecha_str, es_hoy).
    Si hoy tiene citas las retorna; si no, busca el siguiente día con citas
    pendientes o confirmadas.
    """
    citas = list(obtener_citas_del_dia(hoy_str))
    if citas:
        return citas, hoy_str, True

    with get_connection() as conn:
        row = conn.execute(
            """SELECT DISTINCT fecha FROM citas
               WHERE fecha > ? AND estado IN ('pendiente', 'confirmada')
               ORDER BY fecha LIMIT 1""",
            (hoy_str,)
        ).fetchone()

    if row:
        fecha_prox = row["fecha"]
        return list(obtener_citas_del_dia(fecha_prox)), fecha_prox, False

    return [], hoy_str, True


def cancelar_citas_del_dia(fecha):
    """
    Cancela todas las citas pendientes o confirmadas de una fecha.
    Retorna lista de dicts con datos de las citas canceladas (para notificaciones).
    """
    with get_connection() as conn:
        citas = conn.execute(
            """SELECT c.id, c.fecha, c.hora, c.motivo, p.nombre, p.correo
               FROM citas c
               JOIN pacientes p ON c.paciente_id = p.id
               WHERE c.fecha = ? AND c.estado IN ('pendiente', 'confirmada')""",
            (fecha,)
        ).fetchall()

        if citas:
            conn.execute(
                """UPDATE citas SET estado = 'cancelada'
                   WHERE fecha = ? AND estado IN ('pendiente', 'confirmada')""",
                (fecha,)
            )

    return [dict(c) for c in citas]
