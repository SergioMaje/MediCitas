from datetime import date, timedelta
from database import init_db
from pacientes import crear_paciente
from citas import (
    verificar_disponibilidad, crear_cita,
    obtener_citas_del_dia, obtener_citas_semana,
    cambiar_estado, cancelar_cita, slots_disponibles
)

def separador(titulo):
    print(f"\n{'-'*45}")
    print(f"  {titulo}")
    print(f"{'-'*45}")

def ok(msg):  print(f"  [OK]    {msg}")
def falla(msg): print(f"  [FALLA] {msg}")

def proximo_lunes():
    hoy = date.today()
    dias = (7 - hoy.weekday()) % 7
    dias = dias if dias != 0 else 7
    return (hoy + timedelta(days=dias)).strftime("%Y-%m-%d")

# Preparar base de datos limpia
import os
if os.path.exists("medicitas.db"):
    os.remove("medicitas.db")
init_db()
paciente_id = crear_paciente("Laura Torres", "3001234567", "laura@example.com")

LUNES = proximo_lunes()
print(f"\n  Fecha de prueba (lunes): {LUNES}")


# ─────────────────────────────────────────
# 1. verificar_disponibilidad
# ─────────────────────────────────────────
separador("1. verificar_disponibilidad")

# Caso valido: lunes 09:00
result = verificar_disponibilidad(LUNES, "09:00")
(ok if result else falla)(f"Lunes 09:00 disponible -> {result}  (esperado: True)")

# Fuera de horario: lunes 14:00 (entre bloques)
result = verificar_disponibilidad(LUNES, "14:00")
(ok if not result else falla)(f"Lunes 14:00 fuera de horario -> {result}  (esperado: False)")

# Fecha pasada
result = verificar_disponibilidad("2020-01-01", "09:00")
(ok if not result else falla)(f"Fecha pasada -> {result}  (esperado: False)")

# Domingo (sin horario): weekday() 6=domingo, buscamos dias hasta el proximo
hoy = date.today()
dias_hasta_domingo = (6 - hoy.weekday()) % 7
dias_hasta_domingo = dias_hasta_domingo if dias_hasta_domingo != 0 else 7
domingo = (hoy + timedelta(days=dias_hasta_domingo)).strftime("%Y-%m-%d")
result = verificar_disponibilidad(domingo, "09:00")
(ok if not result else falla)(f"Domingo 09:00 -> {result}  (esperado: False)")


# ─────────────────────────────────────────
# 2. crear_cita con validacion
# ─────────────────────────────────────────
separador("2. crear_cita")

id1 = crear_cita(paciente_id, LUNES, "09:00", "Consulta general")
ok(f"Cita creada id={id1} -> {LUNES} 09:00")

# Intentar crear cita en el mismo slot (colision)
try:
    crear_cita(paciente_id, LUNES, "09:00", "Duplicado")
    falla("Debio lanzar ValueError por colision")
except ValueError as e:
    ok(f"Colision detectada: {e}")

# Intentar crear cita fuera de horario
try:
    crear_cita(paciente_id, LUNES, "14:00", "Fuera de horario")
    falla("Debio lanzar ValueError por horario invalido")
except ValueError as e:
    ok(f"Horario invalido detectado: {e}")


# ─────────────────────────────────────────
# 3. obtener_citas_del_dia
# ─────────────────────────────────────────
separador("3. obtener_citas_del_dia")

id2 = crear_cita(paciente_id, LUNES, "10:00", "Control")
citas = obtener_citas_del_dia(LUNES)
ok(f"Citas encontradas para {LUNES}: {len(citas)}")
for c in citas:
    ok(f"  {c['hora']} | {c['nombre']} | {c['motivo']} | {c['estado']}")


# ─────────────────────────────────────────
# 4. obtener_citas_semana
# ─────────────────────────────────────────
separador("4. obtener_citas_semana")

citas_semana = obtener_citas_semana(LUNES)
ok(f"Citas en la semana desde {LUNES}: {len(citas_semana)}")
for c in citas_semana:
    ok(f"  {c['fecha']} {c['hora']} | {c['nombre']}")


# ─────────────────────────────────────────
# 5. cambiar_estado y transiciones
# ─────────────────────────────────────────
separador("5. cambiar_estado")

cambiar_estado(id1, "confirmada")
ok("pendiente -> confirmada: OK")

cambiar_estado(id1, "completada")
ok("confirmada -> completada: OK")

# Transicion invalida: completada -> pendiente
try:
    cambiar_estado(id1, "pendiente")
    falla("Debio lanzar ValueError")
except ValueError as e:
    ok(f"Transicion invalida bloqueada: {e}")


# ─────────────────────────────────────────
# 6. cancelar_cita
# ─────────────────────────────────────────
separador("6. cancelar_cita")

cancelar_cita(id2)
ok(f"Cita id={id2} cancelada")

# El slot debe quedar libre de nuevo
result = verificar_disponibilidad(LUNES, "10:00")
(ok if result else falla)(f"Slot 10:00 libre tras cancelacion -> {result}  (esperado: True)")


# ─────────────────────────────────────────
# 7. slots_disponibles
# ─────────────────────────────────────────
separador("7. slots_disponibles")

slots = slots_disponibles(LUNES)
ok(f"Slots disponibles para {LUNES}: {len(slots)}")
print(f"    {slots[:6]} ...")  # primeros 6 para no saturar la salida


separador("Pruebas completadas")
