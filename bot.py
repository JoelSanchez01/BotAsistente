"""
bot.py — Núcleo del asistente personal de Telegram.

Responsabilidades:
  - Recibir y despachar comandos del usuario a través de handlers.
  - Extraer categorías y fechas del texto libre usando NLP (dateparser).
  - Programar recordatorios puntuales y diarios mediante la job_queue de PTB.
  - Exponer un endpoint /health para que el servicio no duerma en Render.

Modos de ejecución (variable de entorno MODO):
  - "dev"  → Polling (local, sin SSL).
  - "prod" → Webhook sobre aiohttp con /health (Render / cualquier hosting).
"""

import asyncio
import functools
import logging
import os
import re
import signal

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
)
from dotenv import load_dotenv
import dateparser
from dateparser.search import search_dates
from datetime import datetime, time
import pytz

import database as db

# ── Configuración de logging ──────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

# ── Constantes de entorno ─────────────────────────────────────────────────────
TOKEN           = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")   # Solo este ID puede usar el bot

# Zona horaria central — modifica aquí si cambias de región
LOCAL_TZ = pytz.timezone('America/Mexico_City')


# ═══════════════════════════════════════════════════════════════════════════════
# SEGURIDAD
# ═══════════════════════════════════════════════════════════════════════════════

def restricted(func):
    """
    Decorador que bloquea el acceso a cualquier usuario que no sea ALLOWED_USER_ID.
    Si ALLOWED_USER_ID no está configurado, deja pasar a todos (útil en tests).
    """
    @functools.wraps(func)   # Preserva el nombre/docstring de la función original
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if ALLOWED_USER_ID and str(user_id) != str(ALLOWED_USER_ID):
            logging.warning(f"Acceso denegado al usuario: {user_id}")
            return  # Ignora silenciosamente; no revela que el bot existe
        return await func(update, context, *args, **kwargs)
    return wrapped


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS — TAREAS
# ═══════════════════════════════════════════════════════════════════════════════

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de ayuda con todos los comandos disponibles."""
    user = update.effective_user
    logging.info(f"Usuario interactuando ID: {user.id}")
    await update.message.reply_html(
        f"¡Hola {user.mention_html()}! Soy tu asistente personal 🤖.\n\n"
        "<b>🛡️ Seguridad:</b> Acceso autorizado.\n\n"
        "<b>📋 TAREAS INTELIGENTES:</b>\n"
        "/nueva [tarea] #cat [fecha] - <i>Crea tarea y alarma</i>\n"
        "   Ej: <code>/nueva Pagar luz #casa mañana 5pm</code>\n"
        "/pendientes - <i>Ver lista ordenada por urgencia</i>\n"
        "/completar [id] - <i>Marcar tarea como hecha</i>\n"
        "/reporte [mes] - <i>Ver productividad mensual</i>\n\n"
        "<b>🌱 HÁBITOS (Tipos: 'simple' o 'contador'):</b>\n"
        "/habito [nombre] [tipo]\n"
        "   Ej: <code>/habito Leer simple</code> (Sí/No)\n"
        "   Ej: <code>/habito Agua contador</code> (Sumar números)\n"
        "/check [nombre] [cant]\n"
        "   Ej: <code>/check Leer</code> (Listo)\n"
        "   Ej: <code>/check Agua 500</code> (Sumar 500)\n"
        "/rachas - <i>Ver estado actual</i>\n\n"
        "<b>📊 REPORTES FLEXIBLES:</b>\n"
        "/reporte [mes] [año] #categoria\n"
        "   Ej: <code>/reporte</code> (Mes actual)\n"
        "   Ej: <code>/reporte 01</code> (Enero)\n"
        "   Ej: <code>/reporte #trabajo 12 2025</code>\n\n"
        "<b>⏰ HORARIOS AUTOMÁTICOS:</b>\n"
        "☀️ <b>9:00 AM:</b> Resumen de tareas de #Trabajo\n"
        "🌙 <b>8:00 PM:</b> Recordatorio de Hábitos pendientes\n"
        "🔔 <b>Al momento:</b> Tareas con hora específica (ej: '5pm')"
    )


@restricted
async def nueva_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Crea una tarea nueva a partir de texto libre.

    Flujo:
      1. Separa la categoría (#hashtag) del resto del texto.
      2. Usa dateparser para detectar una fecha/hora en lenguaje natural.
      3. Elimina el fragmento de fecha del texto para que no quede en el título.
      4. Guarda en la BD y, si hay fecha, programa un recordatorio exacto.
    """
    raw_text = " ".join(context.args)
    if not raw_text:
        await update.message.reply_text("Uso: /nueva Comprar leche #casa mañana a las 5pm")
        return

    user_id = update.effective_user.id

    # ── Paso 1: extraer la categoría (#hashtag) ───────────────────────────────
    words = raw_text.split()
    categoria = "General"
    clean_words = []
    for word in words:
        if word.startswith("#"):
            categoria = word[1:].capitalize()   # "#casa" → "Casa"
        else:
            clean_words.append(word)
    texto_sin_categoria = " ".join(clean_words)

    # ── Paso 2: detectar fecha en lenguaje natural ────────────────────────────
    settings = {
        'PREFER_DATES_FROM': 'future',        # "lunes" = el próximo lunes
        'DATE_ORDER': 'DMY',                   # Formato latinoamericano
        'TIMEZONE': 'America/Mexico_City',
        'RETURN_AS_TIMEZONE_AWARE': True,      # Devuelve datetime con tzinfo
    }
    fechas_detectadas = search_dates(texto_sin_categoria, languages=['es'], settings=settings) or []

    # Filtrar falsos positivos: un número suelto ("3 mangos") no es una fecha
    fechas_detectadas = [
        (texto, dt) for texto, dt in fechas_detectadas
        if not re.fullmatch(r'\d+', texto.strip())
    ]

    fecha_limite_obj = None
    texto_final = texto_sin_categoria

    if fechas_detectadas:
        # Tomamos la coincidencia más larga: más caracteres = más específica y menos falsos positivos.
        # Ej: "lunes a las 11am" (17 chars) gana sobre "11am" (4 chars) que dateparser
        # malinterpreta como el día 11 del mes en lugar de las 11 AM del lunes.
        fecha_texto, fecha_limite_obj = max(fechas_detectadas, key=lambda x: len(x[0]))
        # ── Paso 3: limpiar el fragmento de fecha del título ─────────────────
        texto_final = ' '.join(texto_sin_categoria.replace(fecha_texto, '').split())
        # Eliminar artículos/preposiciones sueltas que quedan al final tras quitar la fecha.
        # Ej: "Terminar Change el" → "Terminar Change"
        texto_final = re.sub(
            r'\s+\b(para el|hasta el|para la|para|hasta|a las|a la|a|el|la|en|de)\s*$',
            '', texto_final, flags=re.IGNORECASE
        ).strip()
        logging.info(f"Fecha detectada '{fecha_texto}': {fecha_limite_obj}")

    # ── Paso 4: guardar en BD y programar recordatorio ────────────────────────
    db.agregar_tarea(user_id, texto_final, categoria, fecha_limite_obj)
    mensaje = f"✅ Tarea guardada en <b>{categoria}</b>: {texto_final}"

    if fecha_limite_obj:
        mensaje += f"\n📅 Límite: {fecha_limite_obj.strftime('%d/%m/%Y %H:%M')}"
        # run_once dispara task_reminder_callback exactamente en fecha_limite_obj
        context.job_queue.run_once(
            callback=task_reminder_callback,
            when=fecha_limite_obj,
            data={'chat_id': update.effective_chat.id, 'text': texto_final},
            name=f"task_{user_id}_{texto_final[:10]}"  # Nombre único por usuario+tarea
        )
        mensaje += "\n⏰ ¡Recordatorio activado!"

    await update.message.reply_html(mensaje)


async def task_reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback que PTB ejecuta cuando vence el recordatorio de una tarea."""
    job = context.job
    await context.bot.send_message(
        chat_id=job.data['chat_id'],
        text=f"⏰ <b>¡RECORDATORIO!</b>\nEs hora de: {job.data['text']}",
        parse_mode="HTML"
    )


@restricted
async def pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lista las tareas pendientes ordenadas por urgencia:
      🔥 Vencidas → 🚨 Vencen hoy → 📅 Futuras → 🔹 Sin fecha.
    Agrupa el resultado por categoría para mayor legibilidad.
    """
    user_id = update.effective_user.id
    tareas = db.obtener_tareas(user_id)
    if not tareas:
        await update.message.reply_text("🎉 ¡No tienes tareas pendientes!")
        return

    now = datetime.now(LOCAL_TZ)

    # Convertir tuplas de BD a dicts legibles
    lista_tareas = [
        {'id': t[0], 'texto': t[1], 'categoria': t[2], 'limite': t[3]}
        for t in tareas
    ]

    # Las tareas con fecha primero (None va al final), entre ellas por fecha ascendente
    lista_tareas.sort(key=lambda x: (x['limite'] is None, x['limite']))

    # Agrupar por categoría preservando el orden de urgencia
    tareas_por_cat: dict = {}
    for item in lista_tareas:
        tareas_por_cat.setdefault(item['categoria'], []).append(item)

    mensaje = "📝 <b>Tareas Pendientes (Por Urgencia):</b>\n"

    for cat, lista in tareas_por_cat.items():
        mensaje += f"\n📂 <b>{cat}</b>:\n"
        for item in lista:
            limite_str = ""
            icon = "🔹"  # Sin fecha

            if item['limite']:
                # fecha_limite viene como datetime tz-aware desde TIMESTAMPTZ en Postgres
                delta = item['limite'] - now
                if delta.days < 0:
                    icon = "🔥"   # Vencida
                    limite_str = f" (Venció: {item['limite'].strftime('%d/%m')})"
                elif delta.days == 0:
                    icon = "🚨"   # Vence hoy
                    limite_str = f" (HOY: {item['limite'].strftime('%H:%M')})"
                else:
                    icon = "📅"   # Fecha futura
                    limite_str = f" ({item['limite'].strftime('%d/%b')})"

            mensaje += f"  {icon} <code>{item['id']}</code>. {item['texto']}{limite_str}\n"

    await update.message.reply_html(mensaje)


@restricted
async def completar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Marca una tarea como completada.
    La BD valida que la tarea pertenezca al usuario antes de actualizarla.
    """
    if not context.args:
        await update.message.reply_text("Uso: /completar [numero_tarea]")
        return
    try:
        tarea_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Uso: /completar [numero_tarea]")
        return

    user_id = update.effective_user.id
    try:
        db.completar_tarea(tarea_id, user_id)
        await update.message.reply_text(f"✅ Tarea {tarea_id} completada.")
    except ValueError as e:
        # La BD lanza ValueError si la tarea no existe o no pertenece al usuario
        await update.message.reply_text(str(e))


@restricted
async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Genera un reporte mensual de tareas.

    Argumentos opcionales (en cualquier orden):
      - Número 1-12       → mes del reporte
      - Número de 4 cifras → año del reporte
      - #categoria o texto → filtra por categoría
    Ejemplos: /reporte | /reporte 3 | /reporte #trabajo 12 2025
    """
    now = datetime.now(LOCAL_TZ)
    mes, anio = now.month, now.year
    categoria_filtro = None

    args = context.args
    numeric_args = [arg for arg in args if arg.isdigit()]
    text_args    = [arg for arg in args if not arg.isdigit()]

    # Separar mes y año de los argumentos numéricos
    if numeric_args:
        mes_input = int(numeric_args[0])
        if 1 <= mes_input <= 12:
            mes = mes_input
        if len(numeric_args) >= 2:
            anio = int(numeric_args[1])

    # El primer argumento de texto es la categoría (con o sin #)
    if text_args:
        categoria_filtro = text_args[0].lstrip('#').capitalize()

    user_id = update.effective_user.id
    tareas = db.obtener_reporte_mensual(user_id, mes, anio)

    if categoria_filtro:
        tareas = [t for t in tareas if t[2].lower() == categoria_filtro.lower()]

    if not tareas:
        msg_cat = f" de {categoria_filtro}" if categoria_filtro else ""
        await update.message.reply_text(f"No hay actividad{msg_cat} en {mes}/{anio}.")
        return

    # Columnas devueltas por obtener_reporte_mensual:
    # 0:id  1:texto  2:categoria  3:completada(bool)  4:fecha_creacion  5:fecha_completada  6:fecha_limite
    mensaje = f"📊 <b>Reporte {categoria_filtro or 'General'} - {mes}/{anio}</b>\n"
    cats: dict = {}
    total_completadas = total_pendientes = 0

    for t in tareas:
        cat = t[2]
        cats.setdefault(cat, {'hechas': [], 'pendientes': []})
        if t[3]:   # t[3] = completada (Boolean de Postgres)
            cats[cat]['hechas'].append(t)
            total_completadas += 1
        else:
            cats[cat]['pendientes'].append(t)
            total_pendientes += 1

    for cat, data in cats.items():
        mensaje += f"\n📂 <b>{cat.upper()}</b>\n"
        if data['hechas']:
            mensaje += "  ✅ <i>Completadas:</i>\n"
            for t in data['hechas']:
                # t[5] = fecha_completada → datetime tz-aware desde Postgres TIMESTAMPTZ
                fecha_fin = t[5].strftime('%d/%m') if t[5] else ""
                mensaje += f"    • {t[1]} ({fecha_fin})\n"
        if data['pendientes']:
            mensaje += "  ⏳ <i>Pendientes:</i>\n"
            for t in data['pendientes']:
                # t[4] = fecha_creacion → datetime tz-aware desde Postgres TIMESTAMPTZ
                creada = t[4].strftime('%d/%m') if t[4] else ""
                mensaje += f"    • {t[1]} (Del {creada})\n"

    mensaje += (
        f"\n📈 <b>Resumen:</b>\n"
        f"✅ Hechas: {total_completadas}\n"
        f"⏳ Pendientes: {total_pendientes}\n"
        f"Total: {len(tareas)}"
    )

    # Telegram limita los mensajes a 4096 caracteres
    if len(mensaje) > 4000:
        mensaje = mensaje[:4000] + "\n... (reporte truncado)"

    await update.message.reply_html(mensaje)


# ═══════════════════════════════════════════════════════════════════════════════
# HANDLERS — HÁBITOS
# ═══════════════════════════════════════════════════════════════════════════════

@restricted
async def nuevo_habito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Registra un nuevo hábito.

    Tipos:
      - simple   → se marca como hecho o no (binario).
      - contador → acumula un valor numérico (ej: vasos de agua).

    La última palabra del comando define el tipo si coincide con las palabras clave;
    de lo contrario, todo el texto es el nombre y el tipo será 'simple' por defecto.
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: /habito [Nombre del hábito] [tipo: simple/contador]\n"
            "Ej: /habito Leer 30 min simple"
        )
        return

    palabras_tipo = ['simple', 'contador', 'numero', 'num']
    ultimo_arg = args[-1].lower()

    if len(args) > 1 and ultimo_arg in palabras_tipo:
        tipo   = 'contador' if ultimo_arg in ['contador', 'numero', 'num'] else 'simple'
        nombre = " ".join(args[:-1])
    else:
        # Sin tipo explícito → simple por defecto
        tipo   = 'simple'
        nombre = " ".join(args)

    user_id = update.effective_user.id
    try:
        db.crear_habito(user_id, nombre, tipo)
        await update.message.reply_text(
            f"🌱 Hábito creado: <b>{nombre}</b> ({tipo})", parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: Quizás ya existe ese hábito. ({e})")


@restricted
async def check_habito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Registra progreso en un hábito del día de hoy.

    Se puede identificar el hábito por ID numérico o por nombre (parcial o completo).
    Para hábitos de tipo contador se puede indicar la cantidad: /check Agua 500
    """
    args = context.args
    if not args:
        await update.message.reply_text("Uso: /check [ID o Nombre] [cantidad_opcional]")
        return

    identificador = args[0]
    # Si hay un segundo argumento numérico, es la cantidad; si no, se asume 1
    cantidad = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    user_id  = update.effective_user.id
    es_id    = identificador.isdigit()

    exito, msg = db.registrar_progreso_habito(
        user_id,
        int(identificador) if es_id else identificador,
        cantidad,
        es_id=es_id
    )
    await update.message.reply_text(msg + (" 🔥" if exito else ""))


@restricted
async def ver_rachas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado actual de todos los hábitos con su racha de días consecutivos."""
    user_id = update.effective_user.id
    stats = db.obtener_historial_habitos(user_id)

    if not stats:
        await update.message.reply_text("No tienes hábitos. Crea uno con /habito")
        return

    mensaje = "🏆 <b>Mis Hábitos y Rachas</b>\n\n"
    for h in stats:
        # Ícono según tipo: contador muestra la cantidad acumulada hoy
        if h['tipo'] == 'contador':
            check = f"📊 ({h['hoy']})"
        else:
            check = "✅" if h['hoy'] > 0 else "⬜"

        racha_str = f"🔥 {h['racha']} días" if h['racha'] > 0 else "❄️ Sin racha"
        mensaje += f"<b>{h['id']}. {h['nombre']}</b>: {check}\n   Llevas: {racha_str}\n\n"

    mensaje += "Usa /check [ID] para marcar hoy más rápido."
    await update.message.reply_html(mensaje)


# ═══════════════════════════════════════════════════════════════════════════════
# JOBS — RECORDATORIOS AUTOMÁTICOS
# ═══════════════════════════════════════════════════════════════════════════════

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Job diario a las 9:00 AM.
    Envía las tareas pendientes de la categoría 'Trabajo'.
    Solo se ejecuta si hay tareas pendientes para evitar spam.
    """
    if not ALLOWED_USER_ID:
        return
    user_id = int(ALLOWED_USER_ID)

    tareas = db.obtener_tareas(user_id)
    tareas_trabajo = [t for t in tareas if t[2].lower() == "trabajo"]
    if not tareas_trabajo:
        return  # Sin tareas de trabajo, no enviar mensaje vacío

    mensaje = "⏰ <b>Recordatorio de Trabajo (9:00 AM)</b>:\n"
    for t in tareas_trabajo:
        mensaje += f"• {t[1]}\n"
    await context.bot.send_message(chat_id=user_id, text=mensaje, parse_mode="HTML")


async def nightly_habit_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Job diario a las 8:00 PM.
    Recuerda los hábitos que aún no se marcaron hoy.
    Solo se ejecuta si hay hábitos pendientes.
    """
    if not ALLOWED_USER_ID:
        return
    user_id = int(ALLOWED_USER_ID)

    habitos_pendientes = db.obtener_habitos_pendientes_hoy(user_id)
    if not habitos_pendientes:
        return  # Todos los hábitos completos, sin recordatorio

    mensaje = "🌙 <b>Resumen Nocturno: hábitos pendientes</b>\nNo rompas la racha, ¡todavía estás a tiempo! 💪\n\n"
    for nombre in habitos_pendientes:
        mensaje += f"🔘 /check {nombre}\n"
    await context.bot.send_message(chat_id=user_id, text=mensaje, parse_mode="HTML")


@restricted
async def test_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica que el bot puede enviar mensajes proactivos (no solo responder)."""
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="🔔 ¡Test de alarma exitoso! El bot puede enviarte mensajes."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTRUCCIÓN DE LA APLICACIÓN PTB
# ═══════════════════════════════════════════════════════════════════════════════

def _build_app() -> Application:
    """
    Instancia y configura la Application de python-telegram-bot:
      - Registra todos los handlers de comandos.
      - Programa los jobs diarios (9 AM y 8 PM).
    Se llama tanto en modo dev (polling) como en modo prod (webhook).
    """
    defaults = Defaults(tzinfo=LOCAL_TZ)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    # ── Handlers de tareas ────────────────────────────────────────────────────
    app.add_handler(CommandHandler('start',       start))
    app.add_handler(CommandHandler('nueva',       nueva_tarea))
    app.add_handler(CommandHandler('pendientes',  pendientes))
    app.add_handler(CommandHandler('completar',   completar))
    app.add_handler(CommandHandler('reporte',     reporte))

    # ── Handlers de hábitos ───────────────────────────────────────────────────
    app.add_handler(CommandHandler('habito',      nuevo_habito))
    app.add_handler(CommandHandler('check',       check_habito))
    app.add_handler(CommandHandler('rachas',      ver_rachas))

    # ── Utilidades ────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler('test_alarma', test_alarm))

    # ── Jobs diarios (solo si hay un usuario configurado) ────────────────────
    if ALLOWED_USER_ID:
        app.job_queue.run_daily(
            daily_reminder,
            time=time(hour=9, minute=0, second=0, tzinfo=LOCAL_TZ),
            days=(0, 1, 2, 3, 4, 5, 6)   # Todos los días de la semana
        )
        app.job_queue.run_daily(
            nightly_habit_reminder,
            time=time(hour=20, minute=0, second=0, tzinfo=LOCAL_TZ),
            days=(0, 1, 2, 3, 4, 5, 6)
        )
        logging.info(f"Recordatorios diarios configurados en zona horaria: {LOCAL_TZ}")

    return app


# ═══════════════════════════════════════════════════════════════════════════════
# MODO PRODUCCIÓN — servidor aiohttp propio
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_prod(port: int, webhook_url: str) -> None:
    """
    Arranca el bot en modo producción usando aiohttp como servidor web propio.

    Rutas expuestas:
      POST /{TOKEN}  → Recibe los updates que Telegram envía al webhook.
      GET  /health   → Endpoint de salud para que Render/UptimeRobot
                       puedan verificar que el servicio está activo.

    Gestión del ciclo de vida:
      - Escucha SIGTERM y SIGINT para apagarse de forma ordenada (Render lo usa).
      - Elimina el webhook de Telegram al cerrar para evitar errores colgantes.
    """
    application = _build_app()

    # ── Handlers HTTP ─────────────────────────────────────────────────────────

    async def telegram_webhook(request: web.Request) -> web.Response:
        """Recibe el JSON de Telegram, lo deserializa y lo encola en PTB."""
        try:
            data   = await request.json()
            update = Update.de_json(data, application.bot)
            await application.update_queue.put(update)
        except Exception as e:
            logging.error(f"Error procesando update entrante: {e}")
        return web.Response(text="OK")

    async def health_check(request: web.Request) -> web.Response:
        """Responde 200 OK para keep-alive de Render / UptimeRobot."""
        return web.Response(text="OK")

    # ── Servidor aiohttp ──────────────────────────────────────────────────────
    aio_app = web.Application()
    aio_app.router.add_post(f"/{TOKEN}", telegram_webhook)
    aio_app.router.add_get("/health",    health_check)

    runner = web.AppRunner(aio_app)

    # ── Manejo de señales del SO ──────────────────────────────────────────────
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        # Cuando Render apaga el servicio envía SIGTERM; SIGINT es Ctrl+C local
        loop.add_signal_handler(sig, stop_event.set)

    # ── Ciclo de vida ─────────────────────────────────────────────────────────
    async with application:
        await application.start()

        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        # Registrar el webhook en los servidores de Telegram
        full_webhook = f"{webhook_url}/{TOKEN}"
        await application.bot.set_webhook(url=full_webhook)
        logging.info(f"Webhook configurado: {full_webhook}")
        print(f"🚀 Bot activo — puerto {port} — health: {webhook_url}/health")

        await stop_event.wait()   # Mantiene el proceso vivo hasta señal de cierre

        # ── Limpieza ordenada ─────────────────────────────────────────────────
        logging.info("Señal de cierre recibida. Apagando bot...")
        await application.bot.delete_webhook()
        await runner.cleanup()
        await application.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not TOKEN:
        raise SystemExit("❌ Error: TELEGRAM_TOKEN no encontrado en .env")

    # Inicializar tablas y migrar columnas si es necesario
    db.init_db()

    MODO = os.getenv("MODO", "dev")   # Por defecto desarrollo local

    if MODO == "dev":
        print("🤖 Iniciando en modo POLLING (Desarrollo)...")
        _build_app().run_polling()

    elif MODO == "prod":
        PORT = int(os.getenv("PORT", "8443"))

        # Render inyecta RENDER_EXTERNAL_URL automáticamente con la URL pública del servicio.
        # WEBHOOK_URL sirve como alternativa para otros hostings.
        webhook_url = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL")
        if not webhook_url:
            raise SystemExit(
                "❌ Error: configura WEBHOOK_URL o despliega en Render "
                "(provee RENDER_EXTERNAL_URL automáticamente)."
            )

        print("🚀 Iniciando en modo WEBHOOK (Producción)...")
        asyncio.run(_run_prod(PORT, webhook_url.rstrip("/")))

    else:
        raise SystemExit(f"❌ Error: MODO='{MODO}' no reconocido. Usa 'dev' o 'prod'.")
