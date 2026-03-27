from database import get_connection


def get_all():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM pacientes ORDER BY nombre"
        ).fetchall()


def crear_paciente(nombre, telefono=None, correo=None):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pacientes (nombre, telefono, correo) VALUES (?, ?, ?)",
            (nombre, telefono, correo)
        )
        return cursor.lastrowid


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
