"""
database.py — Capa de acceso a datos sobre PostgreSQL.

Responsabilidades:
  - Crear y migrar las tablas al arrancar la aplicación.
  - Proveer funciones CRUD para tareas y hábitos.
  - Gestionar un pool de conexiones para reutilizarlas eficientemente.
  - Aislar toda la lógica SQL del resto de la aplicación.

Notas de diseño:
  - Se usa un context manager `get_db()` que hace commit/rollback automático
    y devuelve la conexión al pool al terminar.
  - Las fechas se almacenan como TIMESTAMPTZ / DATE (tipos nativos de Postgres),
    lo que permite usar EXTRACT, índices y comparaciones de fechas correctamente.
  - La función `_run_migrations` convierte columnas TEXT heredadas al tipo
    correcto sin perder datos, de forma idempotente (puede ejecutarse N veces).
"""

import logging
import os
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import psycopg2
import psycopg2.errors
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

# ── Configuración de conexión ─────────────────────────────────────────────────
DB_URL = os.getenv("DATABASE_URL")

# Pool compartido; se crea la primera vez que se necesita (lazy initialization)
_pool = None


# ═══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DEL POOL DE CONEXIONES
# ═══════════════════════════════════════════════════════════════════════════════

def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """
    Devuelve el pool de conexiones, creándolo si aún no existe.
    ThreadedConnectionPool es seguro para entornos con múltiples hilos,
    como los que usa python-telegram-bot internamente.
    Rango: mínimo 1 conexión activa, máximo 10.
    """
    global _pool
    if _pool is None:
        if not DB_URL:
            raise ValueError("DATABASE_URL no encontrada en .env")
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DB_URL)
    return _pool


@contextmanager
def get_db():
    """
    Context manager para obtener y liberar conexiones del pool de forma segura.

    Valida que la conexión esté viva antes de usarla — Neon.tech cierra
    conexiones inactivas y el pool las retiene sin saberlo.

    Garantías:
      - commit() automático si el bloque termina sin excepción.
      - rollback() automático si ocurre cualquier error.
      - La conexión siempre vuelve al pool (bloque finally).
    """
    pool = _get_pool()
    conn = pool.getconn()

    # Validar que la conexión sigue viva (Neon cierra idle connections)
    if conn.closed:
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    else:
        try:
            conn.cursor().execute("SELECT 1")
        except psycopg2.Error:
            # Conexión muerta — descartarla y pedir una fresca
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
            conn = pool.getconn()

    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass  # La conexión puede estar cerrada, no bloquear por eso
        raise
    finally:
        try:
            pool.putconn(conn)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN Y MIGRACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def _run_migrations(cursor) -> None:
    """
    Convierte columnas de tipos heredados (TEXT, INTEGER) a tipos nativos de Postgres.
    Es idempotente: consulta information_schema antes de ejecutar cada ALTER,
    por lo que se puede llamar en cada arranque sin riesgo.

    Migraciones aplicadas:
      tareas.fecha_creacion   TEXT  → TIMESTAMPTZ
      tareas.fecha_limite     TEXT  → TIMESTAMPTZ
      tareas.fecha_completada TEXT  → TIMESTAMPTZ
      tareas.completada       INT   → BOOLEAN
      habitos.fecha_creacion  TEXT  → DATE
      registros_habitos.fecha TEXT  → DATE
    """
    # Mapa de nombre corto a nombre que devuelve information_schema
    tipo_postgres = {
        'TIMESTAMPTZ': 'timestamp with time zone',
        'BOOLEAN':     'boolean',
        'DATE':        'date',
    }

    migraciones = [
        # (tabla,               columna,            tipo_nuevo,    expresión USING)
        ('tareas',              'fecha_creacion',   'TIMESTAMPTZ', 'fecha_creacion::TIMESTAMPTZ'),
        ('tareas',              'fecha_limite',     'TIMESTAMPTZ', 'fecha_limite::TIMESTAMPTZ'),
        ('tareas',              'fecha_completada', 'TIMESTAMPTZ', 'fecha_completada::TIMESTAMPTZ'),
        ('tareas',              'completada',       'BOOLEAN',     'completada::BOOLEAN'),
        ('habitos',             'fecha_creacion',   'DATE',        'fecha_creacion::DATE'),
        ('registros_habitos',   'fecha',            'DATE',        'fecha::DATE'),
    ]

    for tabla, columna, tipo_nuevo, using in migraciones:
        try:
            # Consultar el tipo actual de la columna en el catálogo de Postgres
            cursor.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """, (tabla, columna))
            fila = cursor.fetchone()

            if fila and fila[0] != tipo_postgres[tipo_nuevo]:
                # La columna existe pero con tipo diferente → migrar
                cursor.execute(
                    f'ALTER TABLE {tabla} ALTER COLUMN {columna} TYPE {tipo_nuevo} USING {using}'
                )
                logging.info(f"Migración aplicada: {tabla}.{columna} → {tipo_nuevo}")
        except Exception as e:
            # Una migración fallida no debe impedir que el bot arranque
            logging.warning(f"Migración {tabla}.{columna} omitida: {e}")


def init_db() -> None:
    """
    Crea las tablas si no existen y aplica migraciones de tipos.
    Debe llamarse una sola vez al arrancar la aplicación (en bot.py __main__).
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # ── Tabla de tareas ───────────────────────────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tareas (
                id               SERIAL PRIMARY KEY,
                user_id          BIGINT       NOT NULL,
                texto            TEXT         NOT NULL,
                categoria        TEXT         DEFAULT 'General',
                fecha_creacion   TIMESTAMPTZ,
                fecha_limite     TIMESTAMPTZ,          -- NULL si no tiene fecha límite
                completada       BOOLEAN      DEFAULT FALSE,
                fecha_completada TIMESTAMPTZ           -- Se llena al completar la tarea
            )
        ''')

        # ── Tabla de hábitos ──────────────────────────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS habitos (
                id             SERIAL PRIMARY KEY,
                user_id        BIGINT   NOT NULL,
                nombre         TEXT     NOT NULL,
                tipo           TEXT     DEFAULT 'simple',   -- 'simple' o 'contador'
                fecha_creacion DATE,
                UNIQUE(user_id, nombre)                     -- Evita duplicados por usuario
            )
        ''')

        # ── Tabla de registros diarios de hábitos ─────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registros_habitos (
                id        SERIAL  PRIMARY KEY,
                habito_id INTEGER REFERENCES habitos(id),
                fecha     DATE    NOT NULL,
                valor     INTEGER DEFAULT 0,
                UNIQUE(habito_id, fecha)   -- Un registro por hábito por día
            )
        ''')

        # Migrar columnas heredadas si la BD ya existía con tipos TEXT/INTEGER
        _run_migrations(cursor)


# ═══════════════════════════════════════════════════════════════════════════════
# TAREAS
# ═══════════════════════════════════════════════════════════════════════════════

def agregar_tarea(user_id: int, texto: str, categoria: str = "General", fecha_limite=None) -> None:
    """Inserta una tarea nueva. fecha_limite puede ser un datetime tz-aware o None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO tareas (user_id, texto, categoria, fecha_creacion, fecha_limite)
               VALUES (%s, %s, %s, %s, %s)''',
            (user_id, texto, categoria, datetime.now(timezone.utc), fecha_limite)
        )


def obtener_tareas(user_id: int, solo_pendientes: bool = True) -> list:
    """
    Devuelve las tareas del usuario.
    Si solo_pendientes=True (por defecto): (id, texto, categoria, fecha_limite)
    Si solo_pendientes=False: (id, texto, categoria, completada, fecha_completada)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if solo_pendientes:
            cursor.execute(
                '''SELECT id, texto, categoria, fecha_limite
                   FROM tareas
                   WHERE user_id = %s AND completada = FALSE''',
                (user_id,)
            )
        else:
            cursor.execute(
                '''SELECT id, texto, categoria, completada, fecha_completada
                   FROM tareas WHERE user_id = %s''',
                (user_id,)
            )
        return cursor.fetchall()


def completar_tarea(tarea_id: int, user_id: int) -> None:
    """
    Marca una tarea como completada.
    Lanza ValueError si la tarea no existe o no pertenece al usuario,
    evitando que un usuario modifique tareas ajenas.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE tareas
               SET completada = TRUE, fecha_completada = %s
               WHERE id = %s AND user_id = %s''',
            (datetime.now(timezone.utc), tarea_id, user_id)
        )
        if cursor.rowcount == 0:
            # rowcount == 0 significa que el WHERE no coincidió con ninguna fila
            raise ValueError(f"Tarea {tarea_id} no encontrada o no te pertenece.")


def obtener_reporte_mensual(user_id: int, mes: int, anio: int) -> list:
    """
    Devuelve todas las tareas (completadas y pendientes) creadas en el mes/año indicado.
    Usa EXTRACT sobre la columna TIMESTAMPTZ para filtrar correctamente.
    Columnas devueltas: id, texto, categoria, completada, fecha_creacion, fecha_completada, fecha_limite
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, texto, categoria, completada,
                      fecha_creacion, fecha_completada, fecha_limite
               FROM tareas
               WHERE user_id = %s
                 AND EXTRACT(MONTH FROM fecha_creacion) = %s
                 AND EXTRACT(YEAR  FROM fecha_creacion) = %s''',
            (user_id, mes, anio)
        )
        return cursor.fetchall()


# ═══════════════════════════════════════════════════════════════════════════════
# HÁBITOS
# ═══════════════════════════════════════════════════════════════════════════════

def crear_habito(user_id: int, nombre: str, tipo: str = 'simple') -> None:
    """
    Crea un hábito nuevo.
    Lanza Exception si ya existe un hábito con ese nombre para este usuario
    (restricción UNIQUE(user_id, nombre) en la BD).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''INSERT INTO habitos (user_id, nombre, tipo, fecha_creacion)
                   VALUES (%s, %s, %s, %s)''',
                (user_id, nombre, tipo, date.today())
            )
        except psycopg2.errors.UniqueViolation:
            # Relanzar con mensaje amigable; el context manager ya hizo rollback
            raise Exception("Ya existe un hábito con ese nombre.")


def registrar_progreso_habito(user_id: int, identificador, valor: int = 1, es_id: bool = False):
    """
    Registra el progreso de un hábito para el día de hoy.

    Búsqueda del hábito:
      - Si es_id=True: busca por ID numérico.
      - Si es_id=False: primero match exacto de nombre (case-insensitive),
        luego match parcial (ILIKE) si no hubo exacto.

    Lógica de actualización:
      - Si ya existe registro hoy y el hábito es 'contador' → suma el valor.
      - Si ya existe y es 'simple' → sobreescribe (re-marcar es idempotente).
      - Si no existe registro hoy → inserta.

    Retorna: (exito: bool, mensaje: str)
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # ── Buscar el hábito ──────────────────────────────────────────────────
        if es_id:
            cursor.execute(
                'SELECT id, tipo, nombre FROM habitos WHERE user_id = %s AND id = %s',
                (user_id, identificador)
            )
            habito = cursor.fetchone()
        else:
            # Prioridad 1: coincidencia exacta (evita ambigüedad con nombres similares)
            cursor.execute(
                'SELECT id, tipo, nombre FROM habitos WHERE user_id = %s AND LOWER(nombre) = LOWER(%s)',
                (user_id, identificador)
            )
            habito = cursor.fetchone()

            if not habito:
                # Prioridad 2: coincidencia parcial como último recurso
                cursor.execute(
                    'SELECT id, tipo, nombre FROM habitos WHERE user_id = %s AND nombre ILIKE %s',
                    (user_id, f"%{identificador}%")
                )
                habito = cursor.fetchone()

        if not habito:
            return False, "No encontré ese hábito."

        habito_id, tipo, nombre_real = habito
        hoy = date.today()

        # ── Verificar si ya hay un registro hoy ──────────────────────────────
        cursor.execute(
            'SELECT id, valor FROM registros_habitos WHERE habito_id = %s AND fecha = %s',
            (habito_id, hoy)
        )
        registro = cursor.fetchone()

        if registro:
            # Ya existe: sumar (contador) o sobreescribir (simple)
            nuevo_valor = (registro[1] + valor) if tipo == 'contador' else valor
            cursor.execute(
                'UPDATE registros_habitos SET valor = %s WHERE id = %s',
                (nuevo_valor, registro[0])
            )
        else:
            # Primera vez hoy: insertar
            nuevo_valor = valor
            cursor.execute(
                'INSERT INTO registros_habitos (habito_id, fecha, valor) VALUES (%s, %s, %s)',
                (habito_id, hoy, valor)
            )

        return True, f"Registrado: {nombre_real} (Total hoy: {nuevo_valor})"


def _calcular_racha(fechas) -> int:
    """
    Calcula cuántos días consecutivos terminan hoy o ayer.

    Algoritmo:
      1. Convierte todas las fechas a objetos date y las deduplica.
      2. Ordena de más reciente a más antigua.
      3. La racha solo es válida si el día más reciente es hoy o ayer;
         de lo contrario el hábito está roto.
      4. Cuenta hacia atrás mientras los días sean consecutivos (diferencia de 1).

    Acepta tanto strings 'YYYY-MM-DD' como objetos date de Postgres.
    """
    if not fechas:
        return 0

    def a_date(f) -> date:
        return f if isinstance(f, date) else datetime.strptime(str(f), '%Y-%m-%d').date()

    fechas_unicas = sorted({a_date(f) for f in fechas}, reverse=True)
    hoy = date.today()

    # La racha se rompe si el último registro no fue hoy ni ayer
    if fechas_unicas[0] not in (hoy, hoy - timedelta(days=1)):
        return 0

    racha = 1
    for i in range(1, len(fechas_unicas)):
        if fechas_unicas[i] == fechas_unicas[i - 1] - timedelta(days=1):
            racha += 1
        else:
            break   # Hueco en la secuencia → racha terminada
    return racha


def obtener_historial_habitos(user_id: int) -> list:
    """
    Devuelve el estado de todos los hábitos del usuario con valor de hoy y racha.

    Optimización: usa solo 2 queries en total independientemente de cuántos
    hábitos tenga el usuario (evita el patrón N+1 del código original).

    Query 1: todos los hábitos + valor de hoy (LEFT JOIN con registros de hoy).
    Query 2: historial completo de todos los hábitos para calcular rachas.

    Retorna lista de dicts: {id, nombre, tipo, hoy, racha}
    """
    with get_db() as conn:
        cursor = conn.cursor()
        hoy = date.today()

        # ── Query 1: hábitos con valor de hoy ────────────────────────────────
        cursor.execute(
            '''SELECT h.id, h.nombre, h.tipo,
                      COALESCE(r_hoy.valor, 0) AS valor_hoy
               FROM habitos h
               LEFT JOIN registros_habitos r_hoy
                   ON r_hoy.habito_id = h.id AND r_hoy.fecha = %s
               WHERE h.user_id = %s
               ORDER BY h.id''',
            (hoy, user_id)
        )
        habitos = cursor.fetchall()

        if not habitos:
            return []

        # ── Query 2: historial de todos los hábitos para calcular rachas ─────
        habito_ids   = [h[0] for h in habitos]
        placeholders = ','.join(['%s'] * len(habito_ids))
        cursor.execute(
            f'''SELECT habito_id, fecha
                FROM registros_habitos
                WHERE habito_id IN ({placeholders}) AND valor > 0
                ORDER BY habito_id, fecha DESC''',
            habito_ids   # psycopg2 acepta lista como secuencia de parámetros
        )

        # Agrupar fechas por hábito para calcular la racha individualmente
        historial: dict = defaultdict(list)
        for habito_id, fecha in cursor.fetchall():
            historial[habito_id].append(fecha)

        return [
            {
                'id':     h_id,
                'nombre': nombre,
                'tipo':   tipo,
                'hoy':    valor_hoy,
                'racha':  _calcular_racha(historial.get(h_id, [])),
            }
            for h_id, nombre, tipo, valor_hoy in habitos
        ]


def obtener_habitos_pendientes_hoy(user_id: int) -> list:
    """
    Devuelve los nombres de los hábitos que NO tienen registro hoy
    (o cuyo valor de hoy es 0). Usado por el recordatorio nocturno.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT h.nombre
               FROM habitos h
               LEFT JOIN registros_habitos r
                   ON h.id = r.habito_id AND r.fecha = %s
               WHERE h.user_id = %s
                 AND (r.valor IS NULL OR r.valor = 0)''',
            (date.today(), user_id)
        )
        return [fila[0] for fila in cursor.fetchall()]
