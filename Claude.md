# Asistente Personal de Telegram — Guía de Desarrollo

Bot personal de Telegram para gestión de tareas y hábitos, construido en Python con PostgreSQL.

## Stack Tecnológico
- **Python 3** con `python-telegram-bot` v20+ (async/await)
- **PostgreSQL** vía `psycopg2-binary` con pool de conexiones
- **aiohttp** como servidor web propio en modo producción (Render)
- **dateparser** para NLP de fechas en español, `pytz` para zona horaria
- **Despliegue:** Render (webhook) o local (polling), controlado por `MODO` en `.env`

## Arquitectura

### `bot.py` — Capa de presentación
- Decorador `@restricted` bloquea silenciosamente usuarios no autorizados (`ALLOWED_USER_ID`)
- Todos los handlers son async y usan `context.job_queue` para recordatorios puntuales
- Jobs diarios: 9:00 AM resumen de tareas `#Trabajo`, 8:00 PM hábitos pendientes
- Modo `prod`: servidor aiohttp propio con rutas `POST /{TOKEN}` y `GET /health`
- Modo `dev`: `run_polling()` estándar de PTB

### `database.py` — Capa de datos
- Pool `ThreadedConnectionPool(1, 10)` compartido; context manager `get_db()` hace commit/rollback automático
- 3 tablas: `tareas`, `habitos`, `registros_habitos`
- `_run_migrations()` idempotente: convierte columnas TEXT heredadas a `TIMESTAMPTZ`/`DATE`/`BOOLEAN` consultando `information_schema`
- Cálculo de rachas en Python (`_calcular_racha`): válida solo si el último registro es hoy o ayer
- `obtener_historial_habitos` usa exactamente 2 queries para N hábitos (evita N+1)

## Variables de Entorno Requeridas
```
TELEGRAM_TOKEN=        # Token del BotFather
ALLOWED_USER_ID=       # ID numérico de Telegram del único usuario autorizado
DATABASE_URL=          # URL de conexión a PostgreSQL (Supabase, Render, etc.)
MODO=dev               # "dev" (polling) o "prod" (webhook)
# Solo para prod:
WEBHOOK_URL=           # O se usa RENDER_EXTERNAL_URL automáticamente
PORT=8443
```

## Comandos del Bot
| Comando | Descripción |
|---|---|
| `/nueva [texto] #cat [fecha]` | Crea tarea con NLP de fecha |
| `/pendientes` | Lista tareas ordenadas por urgencia (🔥🚨📅🔹) |
| `/completar [id]` | Marca tarea como hecha |
| `/reporte [mes] [año] #cat` | Reporte mensual filtrable |
| `/habito [nombre] [simple\|contador]` | Crea hábito nuevo |
| `/check [id o nombre] [cantidad]` | Registra progreso del día |
| `/rachas` | Estado de todos los hábitos con racha |
| `/test_alarma` | Verifica que el bot puede enviar mensajes proactivos |

## Convenciones del Proyecto
- SQL usa `%s` como placeholder (psycopg2, NO `?` de SQLite)
- Las fechas se almacenan como `TIMESTAMPTZ` (aware) en tareas, `DATE` en hábitos/registros
- Categorías: extraídas de `#hashtag` en el texto; default `"General"`
- `tareas.db` y `tareas.db.old` son residuos del SQLite original — ignorar o eliminar
- El `Procfile` define `web: python bot.py`, que en Render activa automáticamente modo `prod`

## Mejoras Pendientes

### Prioridad Alta
1. **Eliminar archivos SQLite residuales** (`tareas.db`, `tareas.db.old`) del repo y del `.gitignore`
2. **Recordatorios perdidos al reiniciar:** los `job_queue.run_once` son en memoria; si el bot se reinicia, los recordatorios de tareas con fecha específica se pierden. Solución: al arrancar, re-programar los recordatorios de tareas futuras consultando la BD.
3. **Zona horaria hardcoded:** `America/Mexico_City` está fija en `LOCAL_TZ`. Moverla a variable de entorno `TIMEZONE` para portabilidad.

### Prioridad Media
4. **Eliminar hábitos/tareas:** No existe comando `/eliminar` ni `/borrar_habito`. El usuario no puede borrar entradas erróneas.
5. **Racha rota en cambio de día:** si el usuario hace `/check` de un hábito a las 11:58 PM y revisa `/rachas` a las 12:01 AM del día siguiente, la racha aparece correcta (ayer cuenta), pero si no hace check ese nuevo día, la racha se rompe sin advertencia visible.
6. **Reporte truncado a 4000 chars:** el corte es abrupto. Mejor paginar o dividir en múltiples mensajes.

### Prioridad Baja
7. **Búsqueda parcial de hábitos con ILIKE:** puede retornar hábito incorrecto si hay nombres similares (ej. "Agua" vs "Agua fría"). Considerar mostrar opciones cuando hay ambigüedad.
8. **Agregar índices en BD:** `tareas(user_id, completada)` y `registros_habitos(habito_id, fecha)` mejorarían consultas frecuentes a escala.
