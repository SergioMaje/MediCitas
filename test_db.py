from database import init_db, get_connection
from pacientes import crear_paciente, obtener_paciente, buscar_pacientes, actualizar_paciente, eliminar_paciente

# ─────────────────────────────────────────
# Utilidad
# ─────────────────────────────────────────
def separador(titulo):
    print(f"\n{'-'*45}")
    print(f"  {titulo}")
    print(f"{'-'*45}")

def ok(msg):  print(f"  [OK] {msg}")
def err(msg): print(f"  [ERROR] {msg}")


# ─────────────────────────────────────────
# 1. Inicializar base de datos
# ─────────────────────────────────────────
separador("1. Inicializar base de datos")
try:
    init_db()
    ok("Base de datos creada / verificada")
except Exception as e:
    err(f"init_db falló: {e}")


# ─────────────────────────────────────────
# 2. Verificar tablas creadas
# ─────────────────────────────────────────
separador("2. Tablas existentes")
with get_connection() as conn:
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for t in tablas:
        ok(t["name"])


# ─────────────────────────────────────────
# 3. Verificar horarios por defecto
# ─────────────────────────────────────────
separador("3. Horarios por defecto")
with get_connection() as conn:
    horarios = conn.execute("SELECT * FROM horarios ORDER BY dia_semana, hora_inicio").fetchall()
    dias = {1:"Lunes", 2:"Martes", 3:"Miercoles", 4:"Jueves", 5:"Viernes", 6:"Sabado"}
    for h in horarios:
        ok(f"{dias[h['dia_semana']]:10} {h['hora_inicio']} - {h['hora_fin']}  ({h['duracion_min']} min)")


# ─────────────────────────────────────────
# 4. Crear pacientes
# ─────────────────────────────────────────
separador("4. Crear pacientes")
id1 = crear_paciente("Ana Garcia",    "3001112233", "ana@example.com")
id2 = crear_paciente("Carlos Ruiz",   "3009998877", "carlos@example.com")
id3 = crear_paciente("Maria Lopez",   "3005556644", "maria@example.com")
ok(f"Ana Garcia    -> id={id1}")
ok(f"Carlos Ruiz   -> id={id2}")
ok(f"Maria Lopez   -> id={id3}")


# ─────────────────────────────────────────
# 5. Obtener paciente por ID
# ─────────────────────────────────────────
separador("5. Obtener paciente por ID")
p = obtener_paciente(id1)
if p:
    ok(f"id={p['id']} | {p['nombre']} | {p['telefono']} | {p['correo']}")
else:
    err(f"No se encontró paciente con id={id1}")


# ─────────────────────────────────────────
# 6. Buscar pacientes
# ─────────────────────────────────────────
separador("6. Buscar por termino")

print("  Busqueda: 'garcia'")
for p in buscar_pacientes("garcia"):
    ok(f"  {p['nombre']} | {p['correo']}")

print("  Busqueda: '300'  (por telefono)")
for p in buscar_pacientes("300"):
    ok(f"  {p['nombre']} | {p['telefono']}")

print("  Busqueda: 'example.com'  (por correo)")
for p in buscar_pacientes("example.com"):
    ok(f"  {p['nombre']} | {p['correo']}")


# ─────────────────────────────────────────
# 7. Actualizar paciente
# ─────────────────────────────────────────
separador("7. Actualizar paciente")
actualizar_paciente(id2, {"telefono": "3110000001", "correo": "carlos_nuevo@example.com"})
p = obtener_paciente(id2)
ok(f"Nuevo telefono: {p['telefono']}")
ok(f"Nuevo correo:   {p['correo']}")


# ─────────────────────────────────────────
# 8. Cascada: eliminar paciente con citas
# ─────────────────────────────────────────
separador("8. Cascada al eliminar paciente")
with get_connection() as conn:
    conn.execute(
        "INSERT INTO citas (paciente_id, fecha, hora, motivo) VALUES (?, ?, ?, ?)",
        (id3, "2026-04-01", "09:00", "Consulta general")
    )
    conn.execute(
        "INSERT INTO citas (paciente_id, fecha, hora, motivo) VALUES (?, ?, ?, ?)",
        (id3, "2026-04-15", "10:00", "Control")
    )
ok(f"2 citas creadas para Maria Lopez (id={id3})")

with get_connection() as conn:
    antes = conn.execute("SELECT COUNT(*) FROM citas WHERE paciente_id=?", (id3,)).fetchone()[0]
ok(f"Citas antes de eliminar: {antes}")

eliminar_paciente(id3)

with get_connection() as conn:
    despues = conn.execute("SELECT COUNT(*) FROM citas WHERE paciente_id=?", (id3,)).fetchone()[0]
    paciente = conn.execute("SELECT COUNT(*) FROM pacientes WHERE id=?", (id3,)).fetchone()[0]
ok(f"Citas despues de eliminar: {despues}")
ok(f"Paciente en tabla:         {paciente}  (0 = eliminado correctamente)")


# ─────────────────────────────────────────
# Resumen final
# ─────────────────────────────────────────
separador("Pruebas completadas")
