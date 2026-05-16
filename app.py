from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from functools import wraps
from datetime import datetime, date, timedelta
import re
import traceback

import config
from database import init_db, get_connection
from scheduler import iniciar as iniciar_scheduler, programar_recordatorio_si_aplica
import pacientes as pac
import citas as cit
import historial as his
from notificaciones import (
    enviar_alerta_medico,
    enviar_cancelacion_por_bloqueo, enviar_confirmacion_medico,
)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

_NOMBRE_RE   = re.compile(r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\-\.']{2,100}$")
_TELEFONO_RE = re.compile(r"^[\d\s\+\-\(\)]{7,20}$")
_CORREO_RE   = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HORA_RE     = re.compile(r"^\d{2}:\d{2}$")


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
# Confirmacion de asistencia del paciente (enlace en recordatorio)
# ─────────────────────────────────────────────────────────────

@app.route("/confirmar/<token>")
def confirmar_asistencia(token):
    respuesta = request.args.get("r", "si")

    with get_connection() as conn:
        cita = conn.execute("""
            SELECT c.id, c.fecha, c.hora, c.estado, c.paciente_confirmo,
                   p.nombre
            FROM citas c JOIN pacientes p ON c.paciente_id = p.id
            WHERE c.token = ?
        """, (token,)).fetchone()

    if not cita:
        return render_template("confirmar.html", estado="invalido")

    if cita["estado"] in ("cancelada", "expirada", "completada"):
        return render_template("confirmar.html", estado="no_activa", cita=dict(cita))

    if cita["paciente_confirmo"] != 0:
        return render_template("confirmar.html", estado="ya_respondida", cita=dict(cita))

    confirmo = 1 if respuesta == "si" else -1
    with get_connection() as conn:
        conn.execute("UPDATE citas SET paciente_confirmo = ? WHERE id = ?",
                     (confirmo, cita["id"]))

    estado_render = "confirmada" if respuesta == "si" else "cancelada_paciente"
    return render_template("confirmar.html", estado=estado_render, cita=dict(cita))


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

        if not _NOMBRE_RE.match(nombre):
            flash("El nombre solo puede contener letras, espacios y guiones (2–100 caracteres).", "danger")
            return render_template("agendar.html")

        if telefono and not _TELEFONO_RE.match(telefono):
            flash("El teléfono solo puede contener dígitos, +, -, () y espacios.", "danger")
            return render_template("agendar.html")

        if not correo:
            flash("El correo electrónico es obligatorio para enviarte la confirmación.", "danger")
            return render_template("agendar.html")

        if not _CORREO_RE.match(correo):
            flash("El correo electrónico no tiene un formato válido.", "danger")
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
            try:
                paciente_id = pac.crear_paciente(nombre, telefono, correo)
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("agendar.html")

        session["paciente_id"]     = paciente_id
        session["paciente_nombre"] = nombre
        session["paciente_correo"] = correo

        return redirect(url_for("agendar_cita"))

    return render_template("agendar.html")


def _ctx_agendar_cita():
    """Contexto de fechas para el template agendar_cita."""
    hoy = date.today()
    return {
        "fecha_min": hoy.strftime("%Y-%m-%d"),
        "fecha_max": (hoy + timedelta(days=config.DIAS_MAX_ANTICIPACION)).strftime("%Y-%m-%d"),
    }


@app.route("/agendar/cita", methods=["GET", "POST"])
def agendar_cita():
    """
    Paso 2: el paciente elige fecha, slot y motivo.
    """
    if not session.get("paciente_id") or session.get("paciente_nombre") is None:
        flash("Tu sesión expiró. Por favor comienza de nuevo.", "warning")
        session.clear()
        return redirect(url_for("agendar"))

    ctx = _ctx_agendar_cita()

    if request.method == "POST":
        fecha  = request.form.get("fecha", "").strip()
        hora   = request.form.get("hora", "").strip()
        motivo = request.form.get("motivo", "").strip()

        if not fecha or not hora:
            flash("Debes seleccionar fecha y hora.", "danger")
            return render_template("agendar_cita.html", **ctx)

        try:
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            flash("El formato de fecha no es válido.", "danger")
            return render_template("agendar_cita.html", **ctx)

        if fecha_dt < date.today():
            flash("La fecha no puede ser en el pasado.", "danger")
            return render_template("agendar_cita.html", **ctx)

        fecha_max = date.today() + timedelta(days=config.DIAS_MAX_ANTICIPACION)
        if fecha_dt > fecha_max:
            flash(f"Solo puedes agendar con un máximo de {config.DIAS_MAX_ANTICIPACION} días de anticipación.", "danger")
            return render_template("agendar_cita.html", **ctx)

        if not _HORA_RE.match(hora):
            flash("El formato de hora no es válido.", "danger")
            return render_template("agendar_cita.html", **ctx)

        slots_validos = cit.slots_disponibles(fecha)
        if hora not in slots_validos:
            flash("La hora seleccionada no está disponible. Elige un horario de la lista.", "danger")
            return render_template("agendar_cita.html", **ctx)

        if len(motivo) > 300:
            flash("El motivo no puede superar los 300 caracteres.", "danger")
            return render_template("agendar_cita.html", **ctx)

        try:
            cita_id = cit.crear_cita(
                session["paciente_id"], fecha, hora, motivo or None
            )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("agendar_cita.html")

        programar_recordatorio_si_aplica(cita_id, fecha, hora)

        # Obtener datos completos para los correos
        datos_cita = {
            "nombre_paciente": session["paciente_nombre"],
            "fecha":  fecha,
            "hora":   hora,
            "motivo": motivo,
            "estado": "pendiente",
        }
        datos_paciente = pac.obtener_paciente(session["paciente_id"])

        enviar_alerta_medico(datos_cita, dict(datos_paciente))

        session.pop("paciente_id",     None)
        session.pop("paciente_nombre", None)
        session.pop("paciente_correo", None)

        flash("Solicitud recibida. Te notificaremos cuando el médico confirme tu cita.", "success")
        return redirect(url_for("agendar_exito"))

    return render_template("agendar_cita.html", **ctx)


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

    today = date.today()
    mes_inicio = today.strftime("%Y-%m-01")
    mes_fin    = today.strftime(f"%Y-%m-{__import__('calendar').monthrange(today.year, today.month)[1]:02d}")

    with __import__("database").get_connection() as conn:
        total_pacientes = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
        citas_hoy       = conn.execute(
            "SELECT COUNT(*) FROM citas WHERE fecha = ? AND estado != 'cancelada'", (hoy,)
        ).fetchone()[0]
        citas_pendientes = conn.execute(
            "SELECT COUNT(*) FROM citas WHERE estado = 'pendiente'"
        ).fetchone()[0]
        # Días del mes con al menos una cita activa (para el mini-calendario)
        dias_con_citas = {
            int(row[0].split("-")[2])
            for row in conn.execute(
                """SELECT DISTINCT fecha FROM citas
                   WHERE fecha BETWEEN ? AND ?
                   AND estado NOT IN ('cancelada', 'expirada')""",
                (mes_inicio, mes_fin)
            ).fetchall()
        }

    proximas_citas, fecha_citas, es_hoy_citas = cit.citas_proxima_fecha(hoy)

    _DIAS  = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    _MESES = ['enero','febrero','marzo','abril','mayo','junio','julio',
              'agosto','septiembre','octubre','noviembre','diciembre']
    _fd = datetime.strptime(fecha_citas, "%Y-%m-%d")
    fecha_citas_fmt = f"{_DIAS[_fd.weekday()]} {_fd.day} de {_MESES[_fd.month - 1]}"

    import calendar as _cal
    cal_weeks = _cal.monthcalendar(today.year, today.month)

    return render_template("panel/dashboard.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes,
        proximas_citas=proximas_citas,
        fecha_citas=fecha_citas,
        fecha_citas_fmt=fecha_citas_fmt,
        es_hoy_citas=es_hoy_citas,
        hoy=hoy,
        cal_weeks=cal_weeks,
        today_day=today.day,
        dias_con_citas=dias_con_citas,
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
        hora_bucket = c["hora"][:2] + ":00"
        citas_grid.setdefault(f, {}).setdefault(hora_bucket, []).append(dict(c))

    # Conteo de citas por día (para badge en header de cada columna)
    citas_por_dia = {
        fecha: sum(len(v) for v in hora_dict.values())
        for fecha, hora_dict in citas_grid.items()
    }

    # Rango de horas dinámico según el horario configurado
    from database import get_connection as _get_conn
    with _get_conn() as conn:
        rango = conn.execute(
            "SELECT MIN(hora_inicio), MAX(hora_fin) FROM horarios WHERE disponible = 1"
        ).fetchone()
    hora_min = int((rango[0] or "08:00").split(":")[0])
    hora_max = int((rango[1] or "19:00").split(":")[0])
    horas = [f"{h:02d}:00" for h in range(hora_min, hora_max + 1)]

    return render_template("panel/calendario.html",
        dias=dias,
        citas_grid=citas_grid,
        citas_por_dia=citas_por_dia,
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

        if nuevo_estado == "confirmada":
            from database import get_connection as _gc
            with _gc() as conn:
                row = conn.execute("""
                    SELECT c.fecha, c.hora, c.motivo, p.nombre, p.correo
                    FROM citas c JOIN pacientes p ON c.paciente_id = p.id
                    WHERE c.id = ?
                """, (cita_id,)).fetchone()
            if row and row["correo"]:
                enviar_confirmacion_medico(
                    {"nombre_paciente": row["nombre"], "fecha": row["fecha"],
                     "hora": row["hora"], "motivo": row["motivo"]},
                    row["correo"]
                )
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(request.referrer or url_for("panel_calendario"))


@app.route("/panel/citas/<int:cita_id>/cancelar", methods=["POST"])
@login_requerido
def cancelar_cita(cita_id):
    try:
        from database import get_connection as _gc
        with _gc() as conn:
            row = conn.execute("""
                SELECT c.fecha, c.hora, c.motivo, p.nombre, p.correo
                FROM citas c JOIN pacientes p ON c.paciente_id = p.id
                WHERE c.id = ?
            """, (cita_id,)).fetchone()
        cit.cancelar_cita(cita_id)
        flash("Cita cancelada.", "success")
        if row and row["correo"]:
            enviar_cancelacion_por_bloqueo(
                {"nombre_paciente": row["nombre"], "fecha": row["fecha"],
                 "hora": row["hora"], "motivo": row["motivo"]},
                row["correo"]
            )
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
        nombre   = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        correo   = request.form.get("correo", "").strip()

        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return render_template("panel/editar_paciente.html", paciente=paciente)

        if not _NOMBRE_RE.match(nombre):
            flash("El nombre solo puede contener letras, espacios y guiones (2–100 caracteres).", "danger")
            return render_template("panel/editar_paciente.html", paciente=paciente)

        if telefono and not _TELEFONO_RE.match(telefono):
            flash("El teléfono solo puede contener dígitos, +, -, () y espacios.", "danger")
            return render_template("panel/editar_paciente.html", paciente=paciente)

        if correo and not _CORREO_RE.match(correo):
            flash("El correo electrónico no tiene un formato válido.", "danger")
            return render_template("panel/editar_paciente.html", paciente=paciente)

        datos = {"nombre": nombre, "telefono": telefono, "correo": correo}
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
# Panel medico — Horarios
# ─────────────────────────────────────────────────────────────

NOMBRES_DIA_SEMANA = {
    1: "Lunes", 2: "Martes", 3: "Miércoles",
    4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"
}

@app.route("/panel/horarios", methods=["GET", "POST"])
@login_requerido
def panel_horarios():
    from database import get_connection

    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "guardar_horario":
            total = int(request.form.get("total_bloques", 0))
            errores = []
            with get_connection() as conn:
                for i in range(total):
                    orig_dia   = request.form.get(f"orig_dia_{i}", "")
                    orig_hora  = request.form.get(f"orig_hora_{i}", "")
                    nueva_ini  = request.form.get(f"hora_inicio_{i}", "").strip()
                    nueva_fin  = request.form.get(f"hora_fin_{i}", "").strip()
                    duracion   = request.form.get(f"duracion_{i}", "30").strip()
                    disponible = 1 if request.form.get(f"disponible_{i}") else 0

                    if not orig_dia or not orig_hora or not nueva_ini or not nueva_fin:
                        continue
                    if nueva_ini >= nueva_fin:
                        errores.append(
                            f"{NOMBRES_DIA_SEMANA.get(int(orig_dia), orig_dia)}: "
                            f"la hora de inicio ({nueva_ini}) debe ser menor que la de fin ({nueva_fin})."
                        )
                        continue
                    try:
                        duracion_int = max(15, int(duracion))
                    except ValueError:
                        duracion_int = 30

                    conn.execute(
                        "DELETE FROM horarios WHERE dia_semana = ? AND hora_inicio = ?",
                        (orig_dia, orig_hora)
                    )
                    conn.execute(
                        """INSERT INTO horarios (dia_semana, hora_inicio, hora_fin, duracion_min, disponible)
                           VALUES (?, ?, ?, ?, ?)""",
                        (orig_dia, nueva_ini, nueva_fin, duracion_int, disponible)
                    )

            if errores:
                for e in errores:
                    flash(e, "danger")
            else:
                flash("Horario semanal actualizado.", "success")

        elif accion == "bloquear":
            fecha   = request.form.get("fecha", "").strip()
            motivo  = request.form.get("motivo", "").strip() or None
            notif   = request.form.get("notificar") == "1"

            if not fecha:
                flash("Debes seleccionar una fecha.", "danger")
            elif fecha < date.today().strftime("%Y-%m-%d"):
                flash("No puedes bloquear una fecha pasada.", "danger")
            else:
                with get_connection() as conn:
                    ya = conn.execute(
                        "SELECT 1 FROM dias_bloqueados WHERE fecha = ?", (fecha,)
                    ).fetchone()

                if ya:
                    flash("Esa fecha ya está bloqueada.", "warning")
                else:
                    citas_canceladas = cit.cancelar_citas_del_dia(fecha)
                    with get_connection() as conn:
                        conn.execute(
                            "INSERT INTO dias_bloqueados (fecha, motivo) VALUES (?, ?)",
                            (fecha, motivo)
                        )
                    if notif:
                        for c in citas_canceladas:
                            if c.get("correo"):
                                enviar_cancelacion_por_bloqueo(
                                    {"nombre_paciente": c["nombre"], "fecha": c["fecha"],
                                     "hora": c["hora"], "motivo": c["motivo"]},
                                    c["correo"]
                                )
                    n = len(citas_canceladas)
                    msg = f"Fecha {fecha} bloqueada."
                    if n:
                        msg += f" {n} cita(s) cancelada(s)."
                        if notif:
                            msg += " Pacientes notificados por correo."
                    flash(msg, "success")

        elif accion == "desbloquear":
            fecha = request.form.get("fecha", "").strip()
            if fecha:
                with get_connection() as conn:
                    conn.execute(
                        "DELETE FROM dias_bloqueados WHERE fecha = ?", (fecha,)
                    )
                flash(f"Fecha {fecha} desbloqueada.", "success")

        return redirect(url_for("panel_horarios"))

    # GET
    from database import get_connection
    with get_connection() as conn:
        horarios_raw = conn.execute(
            "SELECT * FROM horarios ORDER BY dia_semana, hora_inicio"
        ).fetchall()
        dias_bloqueados = conn.execute(
            "SELECT * FROM dias_bloqueados WHERE fecha >= date('now') ORDER BY fecha"
        ).fetchall()

    # Agrupar horarios por día
    from collections import defaultdict
    por_dia = defaultdict(list)
    for h in horarios_raw:
        por_dia[h["dia_semana"]].append(dict(h))
    horarios_agrupados = [(dia, por_dia[dia]) for dia in sorted(por_dia.keys())]

    # Pre-formatear fechas bloqueadas (evita parsing en Jinja)
    _DIAS_ES  = ['lun','mar','mié','jue','vie','sáb','dom']
    _MESES_ES = ['ene','feb','mar','abr','may','jun','jul',
                 'ago','sep','oct','nov','dic']
    dias_bloqueados_list = []
    for d in dias_bloqueados:
        item = dict(d)
        dt = datetime.strptime(item["fecha"], "%Y-%m-%d")
        item["mes_short"]     = _MESES_ES[dt.month - 1]
        item["dia_num"]       = dt.day
        item["fecha_display"] = f"{_DIAS_ES[dt.weekday()]} {dt.day} {_MESES_ES[dt.month-1]}. {dt.year}"
        dias_bloqueados_list.append(item)

    return render_template("panel/horarios.html",
        horarios_agrupados=horarios_agrupados,
        dias_bloqueados=dias_bloqueados_list,
        nombres_dia=NOMBRES_DIA_SEMANA,
    )


# ─────────────────────────────────────────────────────────────
# API — Notificaciones del topbar
# ─────────────────────────────────────────────────────────────

@app.route("/api/notificaciones")
@login_requerido
def api_notificaciones():
    hoy = date.today().strftime("%Y-%m-%d")
    with __import__("database").get_connection() as conn:
        filas = conn.execute("""
            SELECT c.hora, c.estado, p.nombre
            FROM citas c JOIN pacientes p ON c.paciente_id = p.id
            WHERE c.fecha = ? AND c.estado NOT IN ('cancelada', 'expirada', 'completada')
            ORDER BY c.hora
            LIMIT 10
        """, (hoy,)).fetchall()

    resultado = []
    for f in filas:
        estado_label = {"pendiente": "Pendiente", "confirmada": "Confirmada"}.get(f["estado"], f["estado"])
        resultado.append({
            "mensaje": f"{f['nombre']} — {estado_label}",
            "hora": f["hora"],
        })
    return jsonify(resultado)


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
