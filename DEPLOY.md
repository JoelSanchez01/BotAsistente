# Manual de Deploy — Bot Asistente Telegram

## Stack Completo

| Capa | Servicio | Plan |
|---|---|---|
| Código | GitHub — `JoelSanchez01/BotAsistente` | Free |
| Hosting | Render — Web Service | Free |
| Base de datos | Neon.tech — PostgreSQL | Free |
| Keep-alive | UptimeRobot — HTTP Monitor | Free |

---

## Variables de Entorno Requeridas (Render)

| Variable | Valor |
|---|---|
| `TELEGRAM_TOKEN` | Token de @BotFather |
| `ALLOWED_USER_ID` | Tu ID de Telegram (@userinfobot) |
| `DATABASE_URL` | Connection string de Neon.tech |
| `MODO` | `prod` |

> `PORT` y `RENDER_EXTERNAL_URL` los inyecta Render automáticamente.

---

## Dependencias (`requirements.txt`)

```
python-telegram-bot[job-queue]>=20.0
python-dotenv
dateparser
pytz
psycopg2-binary
aiohttp>=3.8.4
```

**Importante:** el extra `[job-queue]` es obligatorio — sin él los recordatorios diarios fallan con `AttributeError: 'NoneType'`.

---

## Procedimiento de Deploy desde Cero

### 1. Base de datos (Neon.tech)
1. Crear proyecto en [neon.tech](https://neon.tech)
2. Copiar el connection string: **Settings → Connection Details → Connection string**
3. Formato: `postgresql://usuario:contraseña@host.neon.tech:5432/neondb`
4. Las tablas se crean solas al primer arranque del bot

### 2. Bot de Telegram
1. Hablar con `@BotFather` → `/newbot`
2. Guardar el token
3. Obtener tu ID: hablar con `@userinfobot` → `/start`

### 3. Render
1. [render.com](https://render.com) → **New → Web Service**
2. Conectar repo `JoelSanchez01/BotAsistente`
3. Configuración:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** Free
4. Agregar las 4 variables de entorno
5. **Deploy**

### 4. UptimeRobot (keep-alive)
1. [uptimerobot.com](https://uptimerobot.com) → **New Monitor**
2. Tipo: **HTTP(s)**
3. URL: `https://botasistente-szfd.onrender.com/health`
4. Intervalo: **5 minutes**
5. Crear monitor — debe aparecer en verde **Up**

---

## Verificación Post-Deploy

| Check | Cómo verificar |
|---|---|
| Bot corriendo | Log de Render muestra `Bot activo — puerto ...` |
| Webhook activo | Log muestra `Webhook configurado: https://...` |
| Health OK | `https://botasistente-szfd.onrender.com/health` responde `OK` |
| BD conectada | Mandar `/start` al bot en Telegram |
| Keep-alive | UptimeRobot muestra estado **Up** en verde |

---

## Errores Comunes y Solución

| Error | Causa | Solución |
|---|---|---|
| `No module named 'aiohttp'` | Dependencias no instaladas | `pip install -r requirements.txt` |
| `AttributeError: 'NoneType' ... run_daily` | Falta `[job-queue]` en requirements | Verificar que diga `python-telegram-bot[job-queue]` |
| Bot arranca en modo POLLING en Render | `MODO` no está en variables de entorno | Agregar `MODO=prod` en Render → Environment |
| `/health` responde 404 | Bot en modo polling (no expone HTTP) | Mismo que arriba |
| `DATABASE_URL no encontrada` | Variable no configurada | Agregar `DATABASE_URL` en Render → Environment |
| Recordatorios no llegan | Bot se reinició (jobs en memoria) | Reiniciar servicio en Render — los jobs diarios se reprograman solos al arrancar |

---

## Redespliegue tras Cambios en el Código

```bash
git add .
git commit -m "descripcion del cambio"
git push origin main
```

Render detecta el push y redeploya automáticamente.
