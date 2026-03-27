# Documento de Requerimientos del Sistema — Medicitas

**Proyecto:** Medicitas — Sistema de Agendamiento de Citas Médicas
**Versión:** 1.0
**Fecha:** 2026-03-26
**Tipo de aplicación:** Aplicación web full-stack (Flask + SQLite)

---

## 1. Descripción General

Medicitas es un sistema web para la gestión de citas médicas de una clínica u consultorio unipersonal. Permite a los pacientes agendar citas de forma autónoma sin necesidad de llamar, y al médico administrar su agenda, historial de pacientes y notificaciones desde un panel privado.

---

## 2. Actores del Sistema

| Actor | Descripción |
|---|---|
| **Paciente** | Persona que reserva una cita médica. No requiere cuenta. |
| **Médico (Admin)** | Usuario autenticado que gestiona citas, pacientes e historial clínico. |
| **Sistema (Scheduler)** | Proceso automatizado que envía recordatorios y expira citas. |

---

## 3. Requerimientos Funcionales

### 3.1 Módulo de Agendamiento (Paciente)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | El sistema debe permitir al paciente registrar sus datos: nombre, teléfono y correo electrónico. | Alta |
| RF-02 | El sistema debe verificar si el paciente ya existe (por correo o teléfono) y reutilizar su registro. | Alta |
| RF-03 | El sistema debe mostrar los horarios disponibles del médico para una fecha seleccionada. | Alta |
| RF-04 | El sistema debe impedir agendar citas en fechas pasadas. | Alta |
| RF-05 | El sistema debe impedir agendar citas en horarios ya ocupados. | Alta |
| RF-06 | El sistema debe impedir agendar citas fuera del horario de atención configurado. | Alta |
| RF-07 | El sistema debe aceptar un motivo de consulta opcional al agendar la cita. | Media |
| RF-08 | Al confirmar la cita, el sistema debe enviar un correo de confirmación al paciente. | Alta |
| RF-09 | Al confirmar la cita, el sistema debe enviar una alerta por correo al médico. | Alta |
| RF-10 | El sistema debe mostrar una página de éxito con el resumen de la cita agendada. | Media |

### 3.2 Módulo de Autenticación (Médico)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-11 | El sistema debe permitir al médico iniciar sesión con usuario y contraseña. | Alta |
| RF-12 | El sistema debe proteger todas las rutas del panel médico con autenticación. | Alta |
| RF-13 | El sistema debe permitir al médico cerrar sesión. | Alta |
| RF-14 | Las credenciales del médico deben configurarse mediante variables de entorno. | Alta |

### 3.3 Módulo de Panel Médico — Dashboard

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-15 | El panel debe mostrar el total de pacientes registrados. | Media |
| RF-16 | El panel debe mostrar el número de citas para el día actual. | Media |
| RF-17 | El panel debe mostrar el número de citas pendientes. | Media |
| RF-18 | El panel debe incluir un mini-calendario mensual de navegación rápida. | Baja |

### 3.4 Módulo de Gestión de Citas (Médico)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-19 | El médico debe poder ver todas las citas organizadas en una vista semanal. | Alta |
| RF-20 | El médico debe poder navegar entre semanas en la vista del calendario. | Alta |
| RF-21 | El médico debe poder cambiar el estado de una cita (pendiente → confirmada). | Alta |
| RF-22 | El médico debe poder cancelar una cita. | Alta |
| RF-23 | El médico debe poder completar una cita e ingresar notas médicas (diagnóstico, tratamiento, medicamentos). | Alta |
| RF-24 | El sistema debe aplicar una máquina de estados para los cambios de estado de citas. | Alta |

**Estados válidos y transiciones:**

```
pendiente → confirmada → completada
         ↘→ cancelada
         ↘→ expirada
confirmada → cancelada
           → expirada
completada → (estado terminal)
cancelada  → (estado terminal)
expirada   → (estado terminal)
```

### 3.5 Módulo de Gestión de Pacientes (Médico)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-25 | El médico debe poder listar todos los pacientes registrados. | Alta |
| RF-26 | El médico debe poder buscar pacientes por nombre, correo o teléfono. | Alta |
| RF-27 | El médico debe poder editar los datos de un paciente (nombre, teléfono, correo). | Media |
| RF-28 | El médico debe poder eliminar un paciente. La eliminación debe ser en cascada (elimina citas e historial). | Media |
| RF-29 | El médico debe poder ver el historial clínico completo de un paciente. | Alta |

### 3.6 Módulo de Historial Clínico

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-30 | Al completar una cita, el sistema debe crear automáticamente un registro en el historial clínico. | Alta |
| RF-31 | El historial debe almacenar: fecha, diagnóstico, tratamiento, medicamentos y notas adicionales. | Alta |
| RF-32 | El historial debe mostrarse en orden cronológico inverso (más reciente primero). | Media |
| RF-33 | Cada registro del historial debe estar vinculado a una cita específica (relación uno a uno). | Alta |

### 3.7 Módulo de Notificaciones por Correo

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-34 | El sistema debe enviar un correo de confirmación al paciente al agendar una cita. | Alta |
| RF-35 | El sistema debe enviar una alerta al médico con los datos del paciente y la cita. | Alta |
| RF-36 | El sistema debe enviar un recordatorio al paciente 24 horas antes de su cita. | Alta |
| RF-37 | El sistema debe usar Gmail (SMTP_SSL, puerto 465) como proveedor de correo. | Alta |
| RF-38 | Los correos deben incluir el nombre de la clínica y datos de contacto. | Media |

### 3.8 Módulo de Scheduler (Automatización)

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-39 | El scheduler debe ejecutarse como proceso daemon en segundo plano. | Alta |
| RF-40 | A las 00:05 diariamente, el sistema debe programar los recordatorios de las citas del día siguiente. | Alta |
| RF-41 | A las 00:10 diariamente, el sistema debe marcar como "expiradas" todas las citas pasadas que no fueron completadas ni canceladas. | Alta |
| RF-42 | El sistema debe evitar el envío duplicado de recordatorios usando un registro en memoria. | Media |

### 3.9 Módulo de Configuración de Horarios

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-43 | El sistema debe soportar un horario de atención configurable por día de la semana. | Alta |
| RF-44 | El horario predeterminado debe ser: Lunes a Viernes 08:00–13:00 y 15:00–18:00; Sábados 08:00–12:00. | Media |
| RF-45 | La duración de cada turno debe ser configurable (por defecto: 30 minutos). | Media |
| RF-46 | El médico debe poder ver la configuración del sistema desde el panel. | Baja |

---

## 4. Requerimientos No Funcionales

### 4.1 Seguridad

| ID | Requerimiento |
|---|---|
| RNF-01 | Las credenciales del médico no deben almacenarse en el código fuente; deben leerse desde variables de entorno (`.env`). |
| RNF-02 | La contraseña del correo electrónico debe ser una "App Password" de Gmail, no la contraseña principal. |
| RNF-03 | El `SECRET_KEY` de Flask debe ser un valor único, largo y aleatorio en producción. |
| RNF-04 | Todas las rutas del panel médico deben estar protegidas con el decorador `@login_requerido`. |
| RNF-05 | El archivo `.env` debe estar listado en `.gitignore` y nunca subirse al repositorio. |
| RNF-06 | Las credenciales por defecto (`admin` / `admin123`) deben cambiarse antes del despliegue en producción. |

### 4.2 Rendimiento

| ID | Requerimiento |
|---|---|
| RNF-07 | El sistema debe responder en menos de 2 segundos para operaciones comunes (listado, agendamiento). |
| RNF-08 | El scheduler debe ejecutarse en un hilo daemon separado para no bloquear la aplicación web. |
| RNF-09 | La base de datos debe tener habilitadas las restricciones de claves foráneas (`PRAGMA foreign_keys = ON`). |

### 4.3 Disponibilidad y Confiabilidad

| ID | Requerimiento |
|---|---|
| RNF-10 | El fallo en el envío de correos no debe interrumpir el flujo de agendamiento; los errores deben registrarse silenciosamente. |
| RNF-11 | El scheduler debe recargar recordatorios pendientes al reiniciar la aplicación para no perder notificaciones programadas. |

### 4.4 Usabilidad

| ID | Requerimiento |
|---|---|
| RNF-12 | El flujo de agendamiento para el paciente no debe requerir creación de cuenta ni inicio de sesión. |
| RNF-13 | El proceso de agendamiento debe completarse en máximo 2 pasos desde el punto de vista del usuario. |
| RNF-14 | La interfaz debe ser accesible desde dispositivos móviles y de escritorio. |
| RNF-15 | Los mensajes de error deben ser claros e informativos para el usuario final. |

### 4.5 Mantenibilidad

| ID | Requerimiento |
|---|---|
| RNF-16 | El sistema debe estar organizado en módulos independientes: `pacientes.py`, `citas.py`, `historial.py`, `notificaciones.py`, `scheduler.py`. |
| RNF-17 | Cada módulo principal debe contar con pruebas unitarias. |
| RNF-18 | La configuración de la aplicación debe centralizarse en `config.py` y el archivo `.env`. |

---

## 5. Requerimientos del Sistema (Técnicos)

### 5.1 Entorno de Ejecución

| Componente | Requisito mínimo |
|---|---|
| Python | 3.7 o superior |
| Sistema operativo | Windows / Linux / macOS |
| Acceso a internet | Requerido para envío de correos |
| Cuenta de Gmail | Con "App Password" habilitada |

### 5.2 Dependencias (requirements.txt)

| Librería | Versión mínima | Propósito |
|---|---|---|
| Flask | >= 3.0.0 | Framework web principal |
| python-dotenv | >= 1.0.0 | Gestión de variables de entorno |
| APScheduler | >= 3.10.0 | Programación de tareas automáticas |
| schedule | >= 1.2.0 | Biblioteca complementaria de scheduling |

### 5.3 Base de Datos

| Aspecto | Detalle |
|---|---|
| Motor | SQLite 3 (archivo local: `medicitas.db`) |
| Inicialización | Automática al arrancar la aplicación |
| Foreign keys | Habilitadas por conexión |
| Respaldo | Manual (copiar el archivo `.db`) |

---

## 6. Modelo de Datos

### Tabla: `pacientes`
| Campo | Tipo | Restricciones |
|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| nombre | TEXT | NOT NULL |
| telefono | TEXT | — |
| correo | TEXT | — |
| fecha_registro | TEXT | DEFAULT: fecha actual |

### Tabla: `citas`
| Campo | Tipo | Restricciones |
|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| paciente_id | INTEGER | FOREIGN KEY → pacientes(id) |
| fecha | TEXT | YYYY-MM-DD, NOT NULL |
| hora | TEXT | HH:MM, NOT NULL |
| motivo | TEXT | Opcional |
| estado | TEXT | DEFAULT: 'pendiente' |

### Tabla: `historial`
| Campo | Tipo | Restricciones |
|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| paciente_id | INTEGER | FOREIGN KEY → pacientes(id) |
| cita_id | INTEGER | UNIQUE, FOREIGN KEY → citas(id) |
| fecha | TEXT | NOT NULL |
| diagnostico | TEXT | Opcional |
| tratamiento | TEXT | Opcional |
| medicamentos | TEXT | Opcional |
| notas | TEXT | Opcional |
| creado_en | TEXT | DEFAULT: datetime actual |

### Tabla: `horarios`
| Campo | Tipo | Restricciones |
|---|---|---|
| dia_semana | INTEGER | 1=Lunes … 6=Sábado, PK compuesta |
| hora_inicio | TEXT | HH:MM, PK compuesta |
| hora_fin | TEXT | HH:MM |
| duracion_min | INTEGER | DEFAULT: 30 |
| disponible | INTEGER | DEFAULT: 1 (booleano) |

---

## 7. Endpoints del Sistema

### Rutas Públicas (Paciente)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Redirección a `/agendar` |
| GET / POST | `/agendar` | Paso 1: Registro del paciente |
| GET / POST | `/agendar/cita` | Paso 2: Selección de fecha, hora y motivo |
| GET | `/agendar/slots?fecha=YYYY-MM-DD` | JSON con slots disponibles |
| GET | `/agendar/exito` | Confirmación exitosa |

### Rutas del Panel Médico (Requieren autenticación)

| Método | Ruta | Descripción |
|---|---|---|
| GET / POST | `/login` | Inicio de sesión del médico |
| GET | `/logout` | Cierre de sesión |
| GET | `/panel` | Dashboard principal |
| GET | `/panel/calendario` | Vista semanal de citas |
| POST | `/panel/citas/<id>/estado` | Cambiar estado de cita |
| POST | `/panel/citas/<id>/cancelar` | Cancelar cita |
| GET / POST | `/panel/citas/<id>/completar` | Completar cita y registrar notas |
| GET | `/panel/pacientes` | Lista y búsqueda de pacientes |
| GET / POST | `/panel/pacientes/<id>/editar` | Editar datos del paciente |
| POST | `/panel/pacientes/<id>/eliminar` | Eliminar paciente (cascada) |
| GET | `/panel/pacientes/<id>/historial` | Historial clínico del paciente |
| GET | `/panel/configuracion` | Configuración del sistema |

---

## 8. Reglas de Negocio

| ID | Regla |
|---|---|
| RN-01 | Solo se pueden agendar citas en fechas futuras (no en el mismo día ni en fechas pasadas). |
| RN-02 | No pueden existir dos citas en el mismo horario (mismo día y misma hora). |
| RN-03 | Las citas solo pueden agendarse dentro del horario de atención configurado en la tabla `horarios`. |
| RN-04 | Un paciente que ya existe (misma combinación de correo o teléfono) no se duplica en la base de datos. |
| RN-05 | Al eliminar un paciente, se eliminan en cascada todas sus citas y su historial clínico. |
| RN-06 | Solo se puede crear un registro de historial por cita (relación uno a uno, campo `cita_id UNIQUE`). |
| RN-07 | Los estados terminales (`completada`, `cancelada`, `expirada`) no pueden cambiar a ningún otro estado. |
| RN-08 | Los recordatorios por correo se envían exactamente 24 horas antes de la cita. |
| RN-09 | El sistema debe evitar enviar el mismo recordatorio más de una vez (deduplicación en memoria). |

---

## 9. Flujos Principales

### Flujo 1: Agendamiento de Cita (Paciente)
```
1. Paciente accede a /agendar
2. Ingresa nombre, teléfono y correo → POST /agendar
3. Sistema busca o crea el registro del paciente
4. Paciente selecciona fecha → AJAX GET /agendar/slots → muestra horarios disponibles
5. Paciente selecciona hora y motivo → POST /agendar/cita
6. Sistema valida disponibilidad (fecha futura, dentro de horario, sin conflicto)
7. Sistema crea la cita con estado "pendiente"
8. Sistema envía correo de confirmación al paciente
9. Sistema envía alerta al médico
10. Redirección a /agendar/exito
```

### Flujo 2: Gestión de Cita (Médico)
```
1. Médico inicia sesión en /login
2. Accede al calendario semanal en /panel/calendario
3. Visualiza citas del día/semana
4. Confirma cita: POST /panel/citas/<id>/estado → estado: "confirmada"
5. Al momento de atender: POST /panel/citas/<id>/completar
6. Ingresa diagnóstico, tratamiento, medicamentos, notas
7. Sistema crea registro en historial y cambia estado a "completada"
```

### Flujo 3: Recordatorio Automático (Sistema)
```
1. Cada día a las 00:05, el scheduler consulta las citas del día siguiente
2. Para cada cita, programa un job que se ejecuta 24 horas antes
3. A la hora programada, el sistema envía correo de recordatorio al paciente
4. El job se elimina del registro para evitar duplicados
```

---

## 10. Variables de Entorno Requeridas

| Variable | Descripción | Ejemplo |
|---|---|---|
| `EMAIL_SENDER` | Correo Gmail remitente | `clinica@gmail.com` |
| `EMAIL_PASSWORD` | App Password de Gmail | `xxxx xxxx xxxx xxxx` |
| `EMAIL_DOCTOR` | Correo del médico (destino de alertas) | `doctor@gmail.com` |
| `CLINICA_NOMBRE` | Nombre de la clínica | `Clínica Medicitas` |
| `CLINICA_TELEFONO` | Teléfono de contacto | `+57 300 000 0000` |
| `DATABASE_PATH` | Ruta al archivo de base de datos | `medicitas.db` |
| `SECRET_KEY` | Clave secreta de Flask | `clave_aleatoria_larga` |
| `DOCTOR_USUARIO` | Usuario del médico para login | `admin` |
| `DOCTOR_PASSWORD` | Contraseña del médico | `password_seguro` |

---

## 11. Pruebas

| Archivo | Módulo probado | Casos principales |
|---|---|---|
| `test_citas.py` | `citas.py` | Disponibilidad, creación, transiciones de estado, detección de conflictos, generación de slots |
| `test_db.py` | `database.py` | Inicialización, estructura de tablas, integridad referencial |
| `test_notificaciones.py` | `notificaciones.py` | Construcción de correos, envío SMTP, manejo de errores |
| `test_scheduler.py` | `scheduler.py` | Programación de recordatorios, carga de pendientes, ejecución |

---

*Documento generado el 2026-03-26 a partir del análisis del código fuente del proyecto Medicitas.*
