from database import get_connection


def crear_registro(paciente_id, cita_id, fecha, diagnostico=None,
                   tratamiento=None, medicamentos=None, notas=None):
    """
    Inserta un registro de historial médico asociado a una cita.
    Retorna el id generado.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO historial
               (paciente_id, cita_id, fecha, diagnostico, tratamiento, medicamentos, notas)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (paciente_id, cita_id, fecha, diagnostico, tratamiento, medicamentos, notas)
        )
        return cursor.lastrowid


def obtener_por_paciente(paciente_id):
    """
    Retorna el historial médico de un paciente en orden cronológico
    descendente. Cada fila incluye el motivo de la cita original.
    """
    with get_connection() as conn:
        return conn.execute(
            """SELECT h.*, c.motivo
               FROM historial h
               JOIN citas c ON h.cita_id = c.id
               WHERE h.paciente_id = ?
               ORDER BY h.fecha DESC, h.creado_en DESC""",
            (paciente_id,)
        ).fetchall()


def obtener_por_cita(cita_id):
    """Retorna el registro de historial de una cita, o None si no existe."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM historial WHERE cita_id = ?", (cita_id,)
        ).fetchone()
