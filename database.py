import sqlite3
from contextlib import contextmanager
from config import DATABASE_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pacientes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre         TEXT    NOT NULL,
                telefono       TEXT,
                correo         TEXT,
                fecha_registro TEXT    NOT NULL DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS citas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                fecha       TEXT    NOT NULL,
                hora        TEXT    NOT NULL,
                motivo      TEXT,
                estado      TEXT    NOT NULL DEFAULT 'pendiente',
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS historial (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id  INTEGER NOT NULL,
                cita_id      INTEGER NOT NULL UNIQUE,
                fecha        TEXT    NOT NULL,
                diagnostico  TEXT,
                tratamiento  TEXT,
                medicamentos TEXT,
                notas        TEXT,
                creado_en    TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE,
                FOREIGN KEY (cita_id)    REFERENCES citas(id)     ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS horarios (
                dia_semana    INTEGER NOT NULL,
                hora_inicio   TEXT    NOT NULL,
                hora_fin      TEXT    NOT NULL,
                duracion_min  INTEGER NOT NULL DEFAULT 30,
                disponible    INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (dia_semana, hora_inicio)
            );
        """)
        _insertar_horarios_defecto(conn)


def _insertar_horarios_defecto(conn):
    existe = conn.execute("SELECT COUNT(*) FROM horarios").fetchone()[0]
    if existe > 0:
        return

    # Lunes a viernes (1-5): 08:00 - 13:00 y 15:00 - 18:00
    # Sabado (6): 08:00 - 12:00
    horarios = []
    for dia in range(1, 6):
        horarios.append((dia, "08:00", "13:00", 30, 1))
        horarios.append((dia, "15:00", "18:00", 30, 1))
    horarios.append((6, "08:00", "12:00", 30, 1))

    conn.executemany(
        "INSERT INTO horarios (dia_semana, hora_inicio, hora_fin, duracion_min, disponible) VALUES (?, ?, ?, ?, ?)",
        horarios
    )
