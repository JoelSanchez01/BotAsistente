# 📖 Manual Completo — Bot Asistente Personal de Telegram

> Este bot vive en Telegram y es tu asistente personal. Te ayuda a **no olvidar tus tareas** y a **mantener hábitos diarios**. Solo tú puedes usarlo — nadie más tiene acceso.

---

## 🧭 ¿Cómo funciona en general?

Abres Telegram, buscas tu bot y le escribes **comandos**. Un comando siempre empieza con `/` (diagonal).

Por ejemplo:
```
/start
```
Eso le dice al bot que quieres ver el menú de ayuda.

Así de simple. No hay botones complicados ni menús ocultos. Solo escribes y el bot responde.

---

## 🚀 Primer paso — `/start`

Escríbele esto al bot cuando entres por primera vez:

```
/start
```

El bot te saludará y te mostrará todos los comandos disponibles. Úsalo cuando no recuerdes cómo se usa algo.

---

---

# 📋 PARTE 1 — TAREAS

Una **tarea** es algo que tienes que hacer: pagar una factura, ir al médico, entregar un trabajo, etc.

El bot te permite:
- ✅ Guardar tus tareas
- 📅 Ponerles fecha límite
- 🔔 Recibir un recordatorio automático
- 🗂️ Organizarlas por categorías
- 📊 Ver reportes de lo que hiciste cada mes

---

## ➕ `/nueva` — Crear una tarea nueva

Este es el comando que más usarás. Sirve para guardar una tarea nueva.

**Cómo se escribe:**
```
/nueva [lo que tienes que hacer] #categoria [cuando]
```

### Ejemplos paso a paso:

---

**Ejemplo 1 — Tarea simple, sin fecha**
```
/nueva Comprar pan
```
✔️ Guarda la tarea "Comprar pan" en la categoría General.
No tiene fecha límite ni recordatorio.

---

**Ejemplo 2 — Tarea con categoría**

Las categorías se escriben con un `#` adelante, sin espacio:
```
/nueva Comprar pan #casa
```
✔️ Guarda "Comprar pan" en la categoría **Casa**.

Puedes usar cualquier categoría que quieras:
`#trabajo` `#casa` `#salud` `#gym` `#finanzas` `#escuela` — lo que necesites.

---

**Ejemplo 3 — Tarea con fecha**
```
/nueva Pagar la renta #casa mañana
```
✔️ Guarda "Pagar la renta" en Casa con fecha de mañana.
Recibirás un recordatorio automático mañana.

---

**Ejemplo 4 — Tarea con fecha y hora exacta**
```
/nueva Llamar al doctor #salud viernes a las 3pm
```
✔️ El viernes a las 3:00 PM el bot te manda un mensaje de alarma.

---

**Ejemplo 5 — Fecha escrita de otra forma**
```
/nueva Entregar reporte #trabajo el 15 de mayo
/nueva Entregar reporte #trabajo 15/05
/nueva Entregar reporte #trabajo en 5 días
/nueva Entregar reporte #trabajo el próximo lunes a las 9am
```
✔️ Todas estas formas funcionan. El bot entiende fechas en español natural.

---

> 💡 **Truco:** El orden no importa demasiado. Puedes poner el `#categoria` al principio, al final o en medio. El bot lo detecta solo.

---

## 📝 `/pendientes` — Ver lo que me falta hacer

Muestra todas tus tareas que aún no has completado.

```
/pendientes
```

**Ejemplo de lo que verás:**
```
📝 Tareas Pendientes (Por Urgencia):

📂 Trabajo:
  🔥 3. Entregar el informe mensual  (Venció: 01/04)
  🚨 7. Reunión con el cliente  (HOY: 15:00)
  📅 9. Preparar presentación  (12/May)

📂 Casa:
  🔹 2. Comprar despensa
  🔹 5. Llamar al plomero
```

### ¿Qué significa cada ícono?

| Ícono | Qué significa | Qué hacer |
|---|---|---|
| 🔥 | La fecha ya **venció** — pasó el plazo | Hazlo cuanto antes o márcala como completada |
| 🚨 | Vence **hoy** | Hazlo hoy |
| 📅 | Tiene fecha en el **futuro** | Está bajo control, pero no la olvides |
| 🔹 | **Sin fecha** asignada | No hay urgencia definida |

> 💡 El número que aparece antes del punto (`3.`, `7.`, `9.`) es el **ID de la tarea**. Lo necesitas para marcarla como completada.

---

## ✅ `/completar` — Marcar una tarea como hecha

Cuando terminas una tarea, dile al bot que ya la hiciste.

**Cómo se escribe:**
```
/completar [número de la tarea]
```

El número lo ves en `/pendientes`.

**Ejemplos:**
```
/completar 3
```
✔️ Marca la tarea número 3 como completada. Desaparece de tu lista de pendientes.

```
/completar 7
```
✔️ Marca la tarea número 7 como completada.

> ⚠️ **Importante:** La tarea no se borra para siempre, queda guardada en la base de datos para que puedas verla en los reportes mensuales.

---

## 📊 `/reporte` — Ver tu productividad del mes

Te muestra un resumen de todo lo que hiciste (y lo que quedó pendiente) en un mes determinado.

**Formas de usarlo:**

```
/reporte
```
✔️ Muestra el reporte del **mes actual**.

```
/reporte 3
```
✔️ Muestra el reporte de **marzo** (del año actual).

```
/reporte 12 2024
```
✔️ Muestra el reporte de **diciembre de 2024**.

```
/reporte #trabajo
```
✔️ Muestra solo las tareas de la categoría **Trabajo** este mes.

```
/reporte #casa 1 2025
```
✔️ Muestra las tareas de **Casa** de **enero de 2025**.

**Ejemplo de lo que verás:**
```
📊 Reporte General - 4/2026

📂 TRABAJO
  ✅ Completadas:
    • Entregar informe (02/04)
    • Reunión mensual (05/04)
  ⏳ Pendientes:
    • Revisar presupuesto (Del 01/04)

📂 CASA
  ✅ Completadas:
    • Pagar renta (01/04)
  ⏳ Pendientes:
    • Llamar al plomero (Del 28/03)

📈 Resumen:
✅ Hechas: 3
⏳ Pendientes: 2
Total: 5
```

---

---

# 🌱 PARTE 2 — HÁBITOS

Un **hábito** es algo que quieres hacer **todos los días**: leer, tomar agua, meditar, hacer ejercicio, etc.

El bot lleva la cuenta de cuántos días seguidos lo has cumplido. A eso se le llama **racha** 🔥.

### Tipos de hábitos

| Tipo | Para qué sirve | Ejemplo |
|---|---|---|
| **Simple** | Lo hiciste o no lo hiciste (sí/no) | Leer, Meditar, Ejercicio |
| **Contador** | Acumulas una cantidad durante el día | Vasos de agua, Pasos, Minutos de ejercicio |

---

## 🌱 `/habito` — Crear un hábito nuevo

**Cómo se escribe:**
```
/habito [nombre del hábito] [tipo]
```

El tipo es opcional — si no lo pones, se crea como **simple** por defecto.

**Ejemplos:**

```
/habito Leer
```
✔️ Crea un hábito **simple** llamado "Leer". Cada día marcas si leíste o no.

```
/habito Meditar simple
```
✔️ Crea un hábito **simple** llamado "Meditar". Igual que el anterior pero siendo explícito.

```
/habito Agua contador
```
✔️ Crea un hábito **contador** llamado "Agua". Cada día vas sumando cuántos mililitros tomaste.

```
/habito Pasos num
```
✔️ También puedes escribir `num` en lugar de `contador`. Hace lo mismo.

> ⚠️ No puedes tener dos hábitos con el mismo nombre. Si intentas crearlo de nuevo, el bot te avisará.

---

## ☑️ `/check` — Registrar que hoy lo hiciste

Este es el comando que usas cada día para decirle al bot que cumpliste tu hábito.

**Cómo se escribe:**
```
/check [nombre o número del hábito]
/check [nombre o número del hábito] [cantidad]
```

### Para hábitos simples:

```
/check Leer
```
✔️ Marca "Leer" como hecho hoy. La racha sigue.

```
/check Meditar
```
✔️ Marca "Meditar" como hecho hoy.

```
/check 1
```
✔️ Hace lo mismo pero usando el **número ID** del hábito en lugar del nombre. Es más rápido cuando ya te lo sabes de memoria. El número lo ves en `/rachas`.

---

### Para hábitos de tipo contador:

```
/check Agua 500
```
✔️ Suma 500 al contador de "Agua" de hoy. (Por ejemplo: tomaste 500ml.)

```
/check Agua 250
```
✔️ Suma 250 más. Si antes sumaste 500, ahora el total del día es 750.

```
/check 3 1000
```
✔️ Suma 1000 al hábito con ID 3. Rápido y directo.

> 💡 Con los contadores puedes ir sumando poco a poco durante el día. No tienes que ponerlo todo de un jalón.

---

### ¿Qué pasa si te equivocas y haces `/check` dos veces?

- En un hábito **simple**: no pasa nada, simplemente lo sobreescribe. Sigue marcado como hecho.
- En un hábito **contador**: suma el valor de nuevo. Ten cuidado de no duplicar.

---

## 🏆 `/rachas` — Ver cómo van tus hábitos

Muestra el estado de todos tus hábitos: si los hiciste hoy y cuántos días seguidos llevas.

```
/rachas
```

**Ejemplo de lo que verás:**
```
🏆 Mis Hábitos y Rachas

1. Leer: ✅
   Llevas: 🔥 12 días

2. Meditar: ⬜
   Llevas: ❄️ Sin racha

3. Agua: 📊 (1500)
   Llevas: 🔥 5 días

4. Ejercicio: ⬜
   Llevas: 🔥 3 días

Usa /check [ID] para marcar hoy más rápido.
```

### ¿Qué significa cada cosa?

| Lo que ves | Qué significa |
|---|---|
| `✅` | Hábito simple — **ya lo hiciste hoy** |
| `⬜` | Hábito simple — **aún no lo haces hoy** |
| `📊 (1500)` | Hábito contador — llevas **1500 acumulados hoy** |
| `🔥 12 días` | Llevas **12 días seguidos** cumpliéndolo |
| `❄️ Sin racha` | No has cumplido el hábito recientemente |

> ⚠️ **Sobre la racha:** Si un día no marcas el hábito, la racha se rompe y vuelve a cero. Pero tienes hasta el final del día — si lo hiciste ayer y hoy aún no, la racha sigue en pie hasta que pase la medianoche.

---

---

# ⏰ PARTE 3 — RECORDATORIOS AUTOMÁTICOS

El bot te manda mensajes solos, sin que tú hagas nada. Estos son fijos:

---

### ☀️ 9:00 AM — Resumen de tareas de Trabajo

Cada mañana a las 9, si tienes tareas pendientes en la categoría **#trabajo**, el bot te las lista:

```
⏰ Recordatorio de Trabajo (9:00 AM):
• Entregar el informe mensual
• Revisar propuesta del cliente
```

> Si no tienes tareas de trabajo pendientes, no te manda nada. Sin spam.

---

### 🌙 8:00 PM — Hábitos que no has marcado hoy

Cada noche a las 8, si tienes hábitos que aún no cumpliste, el bot te avisa:

```
🌙 Resumen Nocturno: hábitos pendientes
No rompas la racha, ¡todavía estás a tiempo! 💪

🔘 /check Leer
🔘 /check Ejercicio
```

> Si ya cumpliste todos tus hábitos, no recibes ningún mensaje. Bien hecho.

---

### 🔔 Alarma exacta — Tareas con hora específica

Si creaste una tarea con hora, el bot te manda una alarma justo en ese momento:

```
⏰ ¡RECORDATORIO!
Es hora de: Llamar al doctor
```

---

---

# 🛠️ PARTE 4 — COMANDOS DE UTILIDAD

### `/test_alarma`

Sirve para comprobar que el bot puede mandarte mensajes aunque no le estés escribiendo tú primero.

```
/test_alarma
```

✔️ El bot te responde con un mensaje de prueba. Si lo recibes, los recordatorios automáticos también funcionarán.

Úsalo después de un reinicio o si sientes que el bot no te está avisando.

---

---

# 📌 RESUMEN RÁPIDO — Todos los comandos de un vistazo

| Comando | Qué hace |
|---|---|
| `/start` | Muestra el menú de ayuda |
| `/nueva [tarea] #cat [fecha]` | Crea una tarea nueva |
| `/pendientes` | Lista tus tareas pendientes por urgencia |
| `/completar [id]` | Marca una tarea como completada |
| `/reporte` | Reporte de productividad del mes |
| `/reporte [mes] [año] #cat` | Reporte filtrado |
| `/habito [nombre] [tipo]` | Crea un hábito nuevo |
| `/check [nombre o id]` | Marca un hábito como hecho hoy |
| `/check [nombre o id] [cantidad]` | Suma cantidad a un hábito contador |
| `/rachas` | Ver estado y rachas de todos los hábitos |
| `/test_alarma` | Probar que el bot funciona correctamente |

---

# ❓ PREGUNTAS FRECUENTES

**¿Puedo usar el bot varias personas?**
No. El bot está configurado para un solo usuario. Si alguien más le escribe, el bot lo ignora sin responder.

**¿Se pierden mis tareas si el bot se reinicia?**
No. Todo está guardado en una base de datos en la nube. Lo que sí se puede perder son los recordatorios con hora exacta — si el bot se reinicia antes de la hora programada, puede que no llegue la alarma.

**¿Puedo borrar una tarea o hábito?**
Por ahora no hay un comando para eso. Es una mejora planeada para el futuro.

**¿El bot funciona aunque no le esté escribiendo?**
Sí. Los recordatorios de las 9 AM y 8 PM llegan solos. Solo necesitas tener Telegram abierto o las notificaciones activas.

**¿Qué pasa si el bot no responde?**
Espera 1-2 minutos — puede estar reiniciándose. Si sigue sin responder, contacta al administrador del bot.
