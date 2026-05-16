import sqlite3
from database import get_connection


def _normalizar_correo(correo):
    return correo.strip().lower() if correo and correo.strip() else None


def get_all():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM pacientes ORDER BY nombre"
        ).fetchall()


def crear_paciente(nombre, telefono=None, correo=None):
    correo = _normalizar_correo(correo)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO pacientes (nombre, telefono, correo) VALUES (?, ?, ?)",
                (nombre, telefono, correo)
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"Ya existe un paciente registrado con el correo '{correo}'.")


def obtener_paciente(id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM pacientes WHERE id = ?",
            (id,)
        ).fetchone()


def buscar_pacientes(termino):
    with get_connection() as conn:
        patron = f"%{termino}%"
        return conn.execute(
            """SELECT * FROM pacientes
               WHERE nombre  LIKE ?
                  OR correo  LIKE ?
                  OR telefono LIKE ?
               ORDER BY nombre""",
            (patron, patron, patron)
        ).fetchall()


def actualizar_paciente(id, datos):
    campos_permitidos = {"nombre", "telefono", "correo"}
    campos = {k: v for k, v in datos.items() if k in campos_permitidos}
    if "correo" in campos:
        campos["correo"] = _normalizar_correo(campos["correo"])

    if not campos:
        return

    setters = ", ".join(f"{campo} = ?" for campo in campos)
    valores = list(campos.values()) + [id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE pacientes SET {setters} WHERE id = ?",
            valores
        )


def eliminar_paciente(id):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM pacientes WHERE id = ?",
            (id,)
        )
