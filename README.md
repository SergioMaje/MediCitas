# Medicitas — Sistema de Gestión de Citas Médicas

Aplicación web para agendamiento de citas médicas en línea. Permite a los pacientes reservar citas de forma autónoma sin necesidad de llamar, y al médico gestionar su agenda, historial de pacientes y notificaciones desde un panel seguro.

---

## Índice

- [Características](#características)
- [Tecnologías](#tecnologías)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Ejecución](#ejecución)
- [Manual de Usuario](#manual-de-usuario)
  - [Para el Paciente](#para-el-paciente)
  - [Para el Médico (Panel de Administración)](#para-el-médico-panel-de-administración)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Base de Datos](#base-de-datos)
- [API de Endpoints](#api-de-endpoints)
- [Sistema de Notificaciones](#sistema-de-notificaciones)
- [Tests](#tests)
- [Consideraciones de Seguridad](#consideraciones-de-seguridad)
- [Despliegue en Producción](#despliegue-en-producción)

---

## Características

- **Agendamiento en 2 pasos** sin necesidad de crear cuenta
- **Panel de administración** con calendario semanal, lista de pacientes y estadísticas
- **Notificaciones automáticas por correo**: confirmación, recordatorio 1 hora antes, alertas al médico
- **Historial clínico** por paciente vinculado a cada cita completada
- **Configuración de horarios** por día de la semana, duración de turnos y bloqueo de fechas
- **Scheduler en segundo plano** para expirar citas pasadas y enviar recordatorios automáticos
- **Logging rotativo** con trazabilidad por módulo

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Backend | Python 3.7+ / Flask 3.0+ |
| Base de datos | SQLite 3 |
| Tareas programadas | APScheduler + schedule |
| Correo electrónico | Gmail SMTP_SSL (puerto 465) |
| Frontend | HTML/CSS/JS + Bootstrap Icons (CDN) |
| Configuración | python-dotenv |

---

## Instalación

**Requisitos previos:** Python 3.7 o superior instalado.

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd medicitas

# 2. Crear entorno virtual (recomendado)
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Configuración

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# --- Correo electrónico ---
EMAIL_SENDER=tu_correo@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   # Contraseña de aplicación de Gmail, NO la principal
EMAIL_DOCTOR=correo_del_medico@gmail.com

# --- Datos de la clínica ---
CLINICA_NOMBRE=Nombre de la Clínica
CLINICA_TELEFONO=+57 300 000 0000

# --- Base de datos ---
DATABASE_PATH=medicitas.db

# --- Seguridad ---
SECRET_KEY=cambia_por_una_clave_segura_y_aleatoria

# --- Acceso al panel médico ---
DOCTOR_USUARIO=admin
DOCTOR_PASSWORD=contraseña_segura

# --- Reglas de agendamiento ---
DIAS_MAX_ANTICIPACION=60     # Días máximos para agendar con antelación
HORAS_MIN_ANTICIPACION=1     # Horas mínimas de anticipación para citas del mismo día
HORAS_RECORDATORIO=1         # Horas antes de la cita para enviar recordatorio
```

### Configurar contraseña de aplicación en Gmail

Para que el sistema pueda enviar correos se necesita una **contraseña de aplicación** (no la contraseña normal de la cuenta):

1. Ir a [myaccount.google.com](https://myaccount.google.com) → Seguridad
2. Activar **Verificación en dos pasos**
3. Buscar **Contraseñas de aplicaciones** y generar una nueva para "Correo / Windows"
4. Copiar la contraseña generada (formato: `xxxx xxxx xxxx xxxx`) en `EMAIL_PASSWORD`

---

## Ejecución

```bash
python app.py
```

La aplicación inicia en `http://localhost:5000` por defecto.

Al arrancar:
- Se inicializa la base de datos y se crean las tablas si no existen
- Se carga el horario por defecto (lunes–viernes 08:00–13:00 / 15:00–18:00, sábado 08:00–12:00)
- Se inicia el scheduler en segundo plano para tareas automáticas

---

## Manual de Usuario

### Para el Paciente

El flujo de agendamiento es completamente público y no requiere registro.

---

#### Paso 1 — Registro del paciente

Acceder a `http://localhost:5000` redirige automáticamente a `/agendar`.

Completar el formulario con:

| Campo | Descripción |
|---|---|
| Nombre completo | Solo letras y espacios, mínimo 2 palabras |
| Teléfono | Solo números, 7–15 dígitos |
| Correo electrónico | Dirección válida donde llegan las notificaciones |

> **Nota:** Si ya existe un paciente con el mismo correo o teléfono, el sistema lo reconoce automáticamente y no duplica el registro.

---

#### Paso 2 — Selección de fecha y hora

Tras registrarse, aparece el calendario de disponibilidad:

1. **Seleccionar una fecha** disponible (resaltada en el calendario)
2. Aparecen los **horarios disponibles** para ese día
3. Seleccionar un **horario**
4. Opcionalmente, escribir el **motivo de la consulta**
5. Confirmar con el botón **Agendar cita**

Restricciones automáticas:
- No se pueden agendar citas en fechas pasadas
- Se respeta el límite mínimo de anticipación configurado
- No se muestran fechas bloqueadas (vacaciones, emergencias)
- Cada paciente puede tener solo una cita pendiente o confirmada por día

---

#### Confirmación y notificaciones

Tras agendar exitosamente:

- Se muestra la **página de éxito** con los datos de la cita
- El paciente recibe un **correo de confirmación** con los detalles y un enlace para confirmar o cancelar asistencia
- El médico recibe una **alerta por correo** con los datos del nuevo paciente

**Recordatorio automático:** 1 hora antes de la cita el paciente recibe un recordatorio por correo.

---

#### Confirmar o cancelar desde el correo

El correo de confirmación incluye un botón/enlace único:

- **Confirmar asistencia** → la cita pasa a estado `confirmada`
- **Cancelar** → la cita pasa a estado `cancelada`

Una vez cancelada, el slot queda disponible para otro paciente.

---

### Para el Médico (Panel de Administración)

Acceso: `http://localhost:5000/login`

Credenciales definidas en `.env` (`DOCTOR_USUARIO` / `DOCTOR_PASSWORD`).

---

#### Dashboard

Vista principal del panel con:

- **Total de pacientes** registrados
- **Citas de hoy** (cantidad)
- **Citas pendientes** pendientes de atención
- **Mini calendario** del mes con indicadores de días con citas
- Acceso rápido a la **próxima fecha con citas**

---

#### Calendario semanal

Ruta: `/panel/calendario`

- Vista en cuadrícula por horas (7 columnas × franjas horarias)
- Navegar entre semanas con los botones `<` y `>`
- Cada cita muestra: nombre del paciente, hora y estado
- Hacer clic en una cita abre las opciones de gestión

---

#### Estados de una cita

Las citas siguen un ciclo de vida definido:

```
pendiente ──► confirmada ──► completada  (terminal)
         └──► cancelada               (terminal)
         └──► expirada                (terminal — asignado automáticamente)
```

Desde el panel se puede:

| Acción | Descripción |
|---|---|
| **Confirmar** | Cambiar estado de `pendiente` a `confirmada` |
| **Cancelar** | Marcar la cita como `cancelada` |
| **Completar** | Marcar la cita como atendida y registrar notas clínicas |

Al **completar** una cita se abre un formulario para registrar:
- Diagnóstico
- Tratamiento indicado
- Medicamentos recetados
- Notas adicionales

Estos datos quedan vinculados al historial del paciente.

---

#### Gestión de pacientes

Ruta: `/panel/pacientes`

- **Buscar** por nombre, correo o teléfono
- **Ver historial** de un paciente (todas sus citas y registros clínicos en orden cronológico inverso)
- **Editar** datos del paciente (nombre, teléfono, correo)
- **Eliminar** un paciente (elimina también todas sus citas e historial clínico)

---

#### Historial clínico

Ruta: `/panel/pacientes/<id>/historial`

Por cada cita completada se muestra:
- Fecha de la consulta
- Diagnóstico
- Tratamiento
- Medicamentos
- Notas adicionales

---

#### Configuración de horarios

Ruta: `/panel/horarios`

**Horario semanal:**
- Activar o desactivar la atención por día de la semana
- Definir hora de inicio y fin de cada turno
- Ajustar la duración de cada slot (por ejemplo, 30 minutos)

**Bloqueo de fechas:**
- Bloquear una fecha específica (vacaciones, emergencias, etc.)
- Opcionalmente notificar por correo a los pacientes con citas en ese día, cancelándolas automáticamente
- Desbloquear fechas previamente bloqueadas

---

#### Configuración del sistema

Ruta: `/panel/configuracion`

Muestra los valores actuales de configuración:
- Nombre y teléfono de la clínica
- Límites de anticipación para agendamiento
- Tiempo de recordatorio
- Cuenta de correo configurada

Para modificarlos, editar el archivo `.env` y reiniciar la aplicación.

---

## Estructura del Proyecto

```
medicitas/
├── app.py                   # Aplicación Flask principal y rutas
├── database.py              # Conexión y creación de tablas SQLite
├── config.py                # Carga de variables de entorno
├── citas.py                 # Lógica de negocio de citas
├── pacientes.py             # CRUD de pacientes
├── historial.py             # Gestión de historial clínico
├── notificaciones.py        # Envío de correos electrónicos
├── scheduler.py             # Tareas automáticas en segundo plano
├── logs.py                  # Configuración de logging
│
├── templates/               # Plantillas Jinja2
│   ├── base.html            # Base pública
│   ├── base_panel.html      # Base del panel de administración
│   ├── agendar.html         # Paso 1: registro de paciente
│   ├── agendar_cita.html    # Paso 2: selección de cita
│   ├── agendar_exito.html   # Confirmación de éxito
│   ├── login.html           # Autenticación del médico
│   ├── confirmar.html       # Respuesta a confirmación del paciente
│   └── panel/
│       ├── dashboard.html
│       ├── calendario.html
│       ├── pacientes.html
│       ├── editar_paciente.html
│       ├── historial_paciente.html
│       ├── completar_cita.html
│       ├── horarios.html
│       └── configuracion.html
│
├── static/
│   └── css/
│       ├── public.css       # Estilos de páginas públicas
│       └── panel.css        # Estilos del panel de administración
│
├── logs/
│   └── medicitas.log        # Log rotativo (5 MB, 3 copias de respaldo)
│
├── medicitas.db             # Base de datos SQLite (creada automáticamente)
├── .env                     # Variables de entorno (no incluido en git)
├── .gitignore
├── requirements.txt
├── REQUERIMIENTOS.md
│
├── test_citas.py
├── test_db.py
├── test_notificaciones.py
├── test_scheduler.py
└── test_flujo_emails.py
```

---

## Base de Datos

La base de datos SQLite se crea automáticamente al iniciar la aplicación.

### Tablas

#### `pacientes`
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador autoincremental |
| `nombre` | TEXT | Nombre completo |
| `telefono` | TEXT | Teléfono de contacto |
| `correo` | TEXT UNIQUE | Correo electrónico (índice único, case-insensitive) |
| `fecha_registro` | TEXT | Fecha de primera consulta |

#### `citas`
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador autoincremental |
| `paciente_id` | INTEGER FK | Referencia a `pacientes.id` (CASCADE) |
| `fecha` | TEXT | Fecha en formato `YYYY-MM-DD` |
| `hora` | TEXT | Hora en formato `HH:MM` |
| `motivo` | TEXT | Motivo de consulta (opcional) |
| `estado` | TEXT | `pendiente`, `confirmada`, `completada`, `cancelada`, `expirada` |
| `token` | TEXT | Token único para confirmar/cancelar desde correo |
| `paciente_confirmo` | INTEGER | `1` = confirmó, `-1` = canceló, `0` = sin respuesta |

#### `historial`
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador autoincremental |
| `paciente_id` | INTEGER FK | Referencia a `pacientes.id` (CASCADE) |
| `cita_id` | INTEGER FK UNIQUE | Referencia a `citas.id` (1 a 1) |
| `fecha` | TEXT | Fecha del registro |
| `diagnostico` | TEXT | Diagnóstico (opcional) |
| `tratamiento` | TEXT | Tratamiento indicado (opcional) |
| `medicamentos` | TEXT | Medicamentos recetados (opcional) |
| `notas` | TEXT | Notas adicionales (opcional) |
| `creado_en` | TEXT | Timestamp de creación |

#### `horarios`
| Columna | Tipo | Descripción |
|---|---|---|
| `dia_semana` | INTEGER PK | `1`=lunes … `6`=sábado |
| `hora_inicio` | TEXT PK | Hora de inicio del slot |
| `hora_fin` | TEXT | Hora de fin del slot |
| `duracion_min` | INTEGER | Duración en minutos (por defecto 30) |
| `disponible` | INTEGER | `1` = habilitado, `0` = deshabilitado |

#### `dias_bloqueados`
| Columna | Tipo | Descripción |
|---|---|---|
| `fecha` | TEXT PK | Fecha bloqueada `YYYY-MM-DD` |
| `motivo` | TEXT | Motivo del bloqueo (opcional) |
| `creado_en` | TEXT | Timestamp de creación |

---

## API de Endpoints

### Públicos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Redirección a `/agendar` |
| GET / POST | `/agendar` | Paso 1: registro del paciente |
| GET / POST | `/agendar/cita` | Paso 2: selección de fecha y hora |
| GET | `/agendar/slots?fecha=YYYY-MM-DD` | JSON con horarios disponibles para una fecha |
| GET | `/agendar/exito` | Página de confirmación de éxito |
| GET | `/confirmar/<token>` | Confirmar o cancelar cita desde enlace de correo |

### Panel (requieren autenticación)

| Método | Ruta | Descripción |
|---|---|---|
| GET / POST | `/login` | Autenticación del médico |
| GET | `/logout` | Cerrar sesión |
| GET | `/panel` | Dashboard con estadísticas |
| GET | `/panel/calendario?semana=YYYY-MM-DD` | Calendario semanal |
| POST | `/panel/citas/<id>/estado` | Cambiar estado de una cita |
| POST | `/panel/citas/<id>/cancelar` | Cancelar una cita |
| GET / POST | `/panel/citas/<id>/completar` | Completar cita y registrar notas clínicas |
| GET | `/panel/pacientes?q=<búsqueda>` | Listar y buscar pacientes |
| GET / POST | `/panel/pacientes/<id>/editar` | Editar datos de un paciente |
| POST | `/panel/pacientes/<id>/eliminar` | Eliminar paciente y su historial |
| GET | `/panel/pacientes/<id>/historial` | Ver historial clínico de un paciente |
| GET / POST | `/panel/horarios` | Configurar horarios y bloquear fechas |
| GET | `/panel/configuracion` | Ver configuración del sistema |

---

## Sistema de Notificaciones

El sistema envía correos electrónicos en los siguientes eventos:

| Evento | Destinatario | Descripción |
|---|---|---|
| Cita agendada | Paciente | Detalles de la cita + enlace de confirmación/cancelación |
| Cita agendada | Médico | Alerta con datos del nuevo paciente |
| Recordatorio | Paciente | 1 hora antes de la cita (configurable) |
| Fecha bloqueada | Paciente | Aviso de cancelación cuando se bloquea un día |

### Scheduler automático

Un hilo daemon ejecuta tareas programadas:

| Hora | Tarea |
|---|---|
| 00:05 diario | Cargar recordatorios para citas de hoy y mañana |
| 00:10 diario | Marcar como `expirada` las citas pasadas sin completar |
| T - 1h por cita | Enviar recordatorio al paciente |

---

## Tests

Ejecutar la suite de pruebas:

```bash
# Todos los tests
python -m pytest

# Un módulo específico
python -m pytest test_citas.py -v

# Con cobertura
python -m pytest --cov=. --cov-report=term-missing
```

| Archivo | Qué prueba |
|---|---|
| `test_citas.py` | Disponibilidad, transiciones de estado, generación de slots |
| `test_db.py` | Inicialización de tablas y esquema |
| `test_notificaciones.py` | Construcción de correos y manejo de errores SMTP |
| `test_scheduler.py` | Programación de tareas y carga de recordatorios |
| `test_flujo_emails.py` | Flujo completo de correos con SMTP simulado |

---

## Consideraciones de Seguridad

- Las credenciales del médico se almacenan en `.env`, nunca en la base de datos
- Autenticación basada en sesión Flask con `SECRET_KEY`
- Todas las consultas SQL usan parámetros para prevenir inyección SQL
- Las entradas de usuario se validan con expresiones regulares
- El `.env` está excluido del repositorio via `.gitignore`
- El correo usa SMTP_SSL con contraseña de aplicación (no la contraseña principal de Gmail)

**Antes de pasar a producción:**
- Cambiar `DOCTOR_USUARIO` y `DOCTOR_PASSWORD` por valores seguros
- Generar un `SECRET_KEY` aleatorio y largo (mínimo 32 caracteres)
- Usar HTTPS con un certificado válido
- Considerar reemplazar SQLite por PostgreSQL para entornos con múltiple concurrencia

---

## Despliegue en Producción

### Con Gunicorn (Linux)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Con Waitress (Windows)

```bash
pip install waitress
waitress-serve --port=8000 app:app
```

### Variables de entorno recomendadas en producción

```env
SECRET_KEY=<cadena_aleatoria_larga>
DOCTOR_USUARIO=<usuario_real>
DOCTOR_PASSWORD=<contraseña_fuerte>
DATABASE_PATH=/ruta/absoluta/medicitas.db
```

> Realizar copias de seguridad periódicas de `medicitas.db`. Es el único archivo que contiene todos los datos de pacientes, citas e historial clínico.

---

## Licencia

Proyecto de uso interno. Ver términos de uso con el equipo de desarrollo.
