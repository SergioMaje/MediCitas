from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from functools import wraps
from datetime import datetime, date, timedelta
import traceback

import config
from database import init_db
from scheduler import iniciar as iniciar_scheduler
import pacientes as pac
import citas as cit
import historial as his
from notificaciones import enviar_confirmacion, enviar_alerta_medico

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


@app.context_processor
def inject_globals():
    return {
        "now":    datetime.now(),
        "config": config,
    }


# ─────────────────────────────────────────────────────────────
# Decorador de proteccion del panel medico
# ─────────────────────────────────────────────────────────────

def login_requerido(f):
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get("autenticado"):
            flash("Debes iniciar sesion para acceder al panel.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorado


# ─────────────────────────────────────────────────────────────
# Autenticacion
# ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("autenticado"):
        return redirect(url_for("panel_dashboard"))

    if request.method == "POST":
        usuario  = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        if usuario == config.DOCTOR_USUARIO and password == config.DOCTOR_PASSWORD:
            session["autenticado"] = True
            flash("Bienvenido al panel.", "success")
            return redirect(url_for("panel_dashboard"))

        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesion cerrada.", "info")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# Ruta raiz
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("agendar"))


# ─────────────────────────────────────────────────────────────
# Flujo publico de agendamiento
# ─────────────────────────────────────────────────────────────

@app.route("/agendar", methods=["GET", "POST"])
def agendar():
    """
    Paso 1: el paciente ingresa sus datos.
    Si ya existe se carga su perfil, si no se crea automaticamente.
    """
    if request.method == "POST":
        nombre   = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        correo   = request.form.get("correo", "").strip()

        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return render_template("agendar.html")

        if not correo:
            flash("El correo electrónico es obligatorio para enviarte la confirmación.", "danger")
            return render_template("agendar.html")

        # Buscar paciente existente por correo o telefono
        paciente = None
        if correo:
            resultados = pac.buscar_pacientes(correo)
            if resultados:
                paciente = resultados[0]

        if not paciente and telefono:
            resultados = pac.buscar_pacientes(telefono)
            if resultados:
                paciente = resultados[0]

        if paciente:
            paciente_id = paciente["id"]
        else:
            paciente_id = pac.crear_paciente(nombre, telefono, correo)

        session["paciente_id"]     = paciente_id
        session["paciente_nombre"] = nombre
        session["paciente_correo"] = correo

        return redirect(url_for("agendar_cita"))

    return render_template("agendar.html")


@app.route("/agendar/cita", methods=["GET", "POST"])
def agendar_cita():
    """
    Paso 2: el paciente elige fecha, slot y motivo.
    """
    if not session.get("paciente_id"):
        return redirect(url_for("agendar"))

    if request.method == "POST":
        fecha  = request.form.get("fecha", "").strip()
        hora   = request.form.get("hora", "").strip()
        motivo = request.form.get("motivo", "").strip()

        if not fecha or not hora:
            flash("Debes seleccionar fecha y hora.", "danger")
            return render_template("agendar_cita.html")

        try:
            cita_id = cit.crear_cita(
                session["paciente_id"], fecha, hora, motivo or None
            )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("agendar_cita.html")

        # Obtener datos completos para los correos
        datos_cita = {
            "nombre_paciente": session["paciente_nombre"],
            "fecha":  fecha,
            "hora":   hora,
            "motivo": motivo,
            "estado": "pendiente",
        }
        datos_paciente = pac.obtener_paciente(session["paciente_id"])

        if session.get("paciente_correo"):
            enviar_confirmacion(datos_cita, session["paciente_correo"])

        enviar_alerta_medico(datos_cita, dict(datos_paciente))

        session.pop("paciente_id",     None)
        session.pop("paciente_nombre", None)
        session.pop("paciente_correo", None)

        flash("Cita agendada correctamente. Revisa tu correo para la confirmacion.", "success")
        return redirect(url_for("agendar_exito"))

    return render_template("agendar_cita.html")


@app.route("/agendar/slots")
def slots_disponibles():
    """Endpoint JSON que retorna los slots libres para una fecha."""
    fecha = request.args.get("fecha", "")
    if not fecha:
        return jsonify([])
    try:
        slots = cit.slots_disponibles(fecha)
        return jsonify(slots)
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Error al obtener slots"}), 500


@app.route("/agendar/exito")
def agendar_exito():
    return render_template("agendar_exito.html")


# ─────────────────────────────────────────────────────────────
# Panel medico — Dashboard
# ─────────────────────────────────────────────────────────────

@app.route("/panel")
@login_requerido
def panel_dashboard():
    hoy = date.today().strftime("%Y-%m-%d")

    with __import__("database").get_connection() as conn:
        total_pacientes = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
        citas_hoy       = conn.execute(
            "SELECT COUNT(*) FROM citas WHERE fecha = ? AND estado != 'cancelada'", (hoy,)
        ).fetchone()[0]
        citas_pendientes = conn.execute(
            "SELECT COUNT(*) FROM citas WHERE estado = 'pendiente'"
        ).fetchone()[0]

    proximas_citas = cit.obtener_citas_del_dia(hoy)

    import calendar as _cal
    today = date.today()
    # Build calendar weeks for the mini-calendar
    cal_weeks = _cal.monthcalendar(today.year, today.month)

    return render_template("panel/dashboard.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes,
        proximas_citas=proximas_citas,
        hoy=hoy,
        cal_weeks=cal_weeks,
        today_day=today.day,
    )


# ─────────────────────────────────────────────────────────────
# Panel medico — Calendario
# ─────────────────────────────────────────────────────────────

@app.route("/panel/calendario")
@login_requerido
def panel_calendario():
    hoy = date.today()

    # Semana: acepta ?semana=YYYY-MM-DD (lunes de la semana deseada)
    semana_str = request.args.get("semana", "")
    try:
        lunes = datetime.strptime(semana_str, "%Y-%m-%d").date()
        # Ajustar al lunes real de esa semana
        lunes = lunes - timedelta(days=lunes.weekday())
    except ValueError:
        lunes = hoy - timedelta(days=hoy.weekday())

    domingo = lunes + timedelta(days=6)
    sem_prev = (lunes - timedelta(days=7)).strftime("%Y-%m-%d")
    sem_next = (lunes + timedelta(days=7)).strftime("%Y-%m-%d")

    NOMBRES_DIA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    dias = []
    for i in range(7):
        d = lunes + timedelta(days=i)
        dias.append({
            "fecha":  d.strftime("%Y-%m-%d"),
            "nombre": NOMBRES_DIA[i],
            "numero": d.day,
            "es_hoy": d == hoy,
        })

    todas = cit.obtener_citas_semana(lunes.strftime("%Y-%m-%d"))

    # Grid: citas_grid[fecha][hora_bucket] = [lista de citas]
    citas_grid = {}
    for c in todas:
        f = c["fecha"]
        hora_bucket = c["hora"][:3] + "00"
        citas_grid.setdefault(f, {}).setdefault(hora_bucket, []).append(dict(c))

    horas = [f"{h:02d}:00" for h in range(8, 20)]

    return render_template("panel/calendario.html",
        dias=dias,
        citas_grid=citas_grid,
        horas=horas,
        sem_prev=sem_prev,
        sem_next=sem_next,
        lunes=lunes,
        domingo=domingo,
        hoy=hoy.strftime("%Y-%m-%d"),
    )


@app.route("/panel/citas/<int:cita_id>/estado", methods=["POST"])
@login_requerido
def cambiar_estado_cita(cita_id):
    nuevo_estado = request.form.get("estado", "").strip()
    if nuevo_estado == "completada":
        return redirect(url_for("completar_cita", cita_id=cita_id))
    try:
        cit.cambiar_estado(cita_id, nuevo_estado)
        flash(f"Estado actualizado a '{nuevo_estado}'.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(request.referrer or url_for("panel_calendario"))


@app.route("/panel/citas/<int:cita_id>/cancelar", methods=["POST"])
@login_requerido
def cancelar_cita(cita_id):
    try:
        cit.cancelar_cita(cita_id)
        flash("Cita cancelada.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(request.referrer or url_for("panel_calendario"))


# ─────────────────────────────────────────────────────────────
# Panel medico — Completar cita + historial
# ─────────────────────────────────────────────────────────────

@app.route("/panel/citas/<int:cita_id>/completar", methods=["GET", "POST"])
@login_requerido
def completar_cita(cita_id):
    with __import__("database").get_connection() as conn:
        cita = conn.execute(
            """SELECT c.*, p.nombre, p.correo, p.telefono
               FROM citas c JOIN pacientes p ON c.paciente_id = p.id
               WHERE c.id = ?""",
            (cita_id,)
        ).fetchone()

    if not cita:
        flash("Cita no encontrada.", "danger")
        return redirect(url_for("panel_dashboard"))

    if cita["estado"] != "confirmada":
        flash("Solo se pueden completar citas confirmadas.", "warning")
        return redirect(url_for("panel_dashboard"))

    if request.method == "POST":
        diagnostico  = request.form.get("diagnostico", "").strip() or None
        tratamiento  = request.form.get("tratamiento", "").strip() or None
        medicamentos = request.form.get("medicamentos", "").strip() or None
        notas        = request.form.get("notas", "").strip() or None

        try:
            cit.cambiar_estado(cita_id, "completada")
            his.crear_registro(
                paciente_id  = cita["paciente_id"],
                cita_id      = cita_id,
                fecha        = cita["fecha"],
                diagnostico  = diagnostico,
                tratamiento  = tratamiento,
                medicamentos = medicamentos,
                notas        = notas,
            )
            flash("Cita completada y registro guardado.", "success")
        except ValueError as e:
            flash(str(e), "danger")

        return redirect(url_for("panel_dashboard"))

    return render_template("panel/completar_cita.html", cita=cita)


# ─────────────────────────────────────────────────────────────
# Panel medico — Pacientes
# ─────────────────────────────────────────────────────────────

@app.route("/panel/pacientes")
@login_requerido
def panel_pacientes():
    termino   = request.args.get("q", "").strip()
    pacientes = pac.buscar_pacientes(termino) if termino else pac.get_all()
    return render_template("panel/pacientes.html", pacientes=pacientes, termino=termino)


@app.route("/panel/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
@login_requerido
def editar_paciente(paciente_id):
    paciente = pac.obtener_paciente(paciente_id)
    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for("panel_pacientes"))

    if request.method == "POST":
        datos = {
            "nombre":   request.form.get("nombre", "").strip(),
            "telefono": request.form.get("telefono", "").strip(),
            "correo":   request.form.get("correo", "").strip(),
        }
        pac.actualizar_paciente(paciente_id, datos)
        flash("Paciente actualizado.", "success")
        return redirect(url_for("panel_pacientes"))

    return render_template("panel/editar_paciente.html", paciente=paciente)


@app.route("/panel/pacientes/<int:paciente_id>/historial")
@login_requerido
def historial_paciente(paciente_id):
    paciente = pac.obtener_paciente(paciente_id)
    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for("panel_pacientes"))
    registros = his.obtener_por_paciente(paciente_id)
    return render_template("panel/historial_paciente.html",
                           paciente=paciente, registros=registros)


@app.route("/panel/pacientes/<int:paciente_id>/eliminar", methods=["POST"])
@login_requerido
def eliminar_paciente(paciente_id):
    pac.eliminar_paciente(paciente_id)
    flash("Paciente eliminado junto con sus citas.", "success")
    return redirect(url_for("panel_pacientes"))


# ─────────────────────────────────────────────────────────────
# Panel medico — Configuracion
# ─────────────────────────────────────────────────────────────

@app.route("/panel/configuracion")
@login_requerido
def panel_configuracion():
    return render_template("panel/configuracion.html", config=config)


# ─────────────────────────────────────────────────────────────
# Arranque
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    iniciar_scheduler()
    app.run(debug=True)
