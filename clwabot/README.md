# clwabot

Asistente local para stredes integrado con OpenClaw (ares_mers).

Componentes:
- Capa OSCP (plan de estudio, tracking de labs)
- Capa VIP / auto-respuestas (contactos especiales, mensajes programados)
- Capa de reportes tácticos diarios

Este proyecto está pensado para ser consumido por OpenClaw (Ares) vía scripts/comandos.

## Router unificado (conecta todo)

Arranque recomendado en runtime:

```bash
openclaw logs --follow | python3 -m clwabot.hooks.whatsapp_router_watch
```

Compatibilidad legacy:

```bash
python3 -m clwabot.core.ares_listener
```

Este router envía todos los inbound de WhatsApp al `whatsapp_listener`, que luego decide:
- owner -> no auto-respuesta
- VIP urgencias -> protocolo 1-4
- externos -> formulario de reunión con gate de 15s y presencia owner

### Ejecutarlo 24/7 con systemd --user

Servicio instalado: `clwabot-router.service`

Comandos útiles:

```bash
systemctl --user status clwabot-router.service
systemctl --user restart clwabot-router.service
journalctl --user -u clwabot-router.service -f
```

## Protocolo de Urgencias (VIP)

El flujo de urgencias incluye:

- Catálogo 1-4 (evento, nota, recordatorio, inmediata)
- Confirmación antes de notificar al owner
- Comandos de control en sesión: `cancelar`, `volver`, `cambiar a <1-4>`
- Parser básico de fecha/hora en español (`mañana 19:30`, `lunes 10:00`, `20/03 09:00`)
- Detección de duplicados en ventana corta para evitar spam
- Escalado automático para opción `4` (reintento al owner con delay)
- Dedupe semántico para evitar spam repetido

## Agendamiento de reuniones (contactos externos)

Cuando un contacto externo escribe con intención de agenda (`reunión`, `agendar`, `meeting`, etc.):

- Espera 15s antes de activar auto-respuesta.
- Si el owner está activo en ese intervalo, no dispara el protocolo (se mantiene natural).
- Se activa un formulario conversacional guiado.
- El agente se presenta y da ejemplo.
- Recolecta: tema, fecha, hora, duración y modalidad.
- Pide confirmación final.
- Genera `.ics` y lo envía al contacto y al owner.
- Encola sync externo de calendario en `data/google_calendar_queue.json`
- Programa follow-up automático post-agendamiento (24h)

## Control del asistente (owner)

Comandos por WhatsApp:

- `/status`
- `/pausar` y `/reanudar`
- `/modo normal|busy|vacation`
- `/horario HH:MM HH:MM`
- `/forzar-reunion +MSISDN`
- `/ayuda`

Comandos OSCP:

- `/oscp-status` (avance y focos débiles)
- `/oscp-plan` (plan semanal por horas)
- `/oscp-next` (siguiente acción recomendada)
- `/oscp-labs` (resumen de labs)
- `/oscp-lab <nombre> <pending|in_progress|rooted>` (cambiar estado)
- `/oscp-note <lab> | <nota>` (agregar nota operativa)

## Memoria y métricas

- Memoria por contacto en `data/state.json` (`contacts.*`)
- Métricas de eventos en `data/state.json` (`metrics.events`)
- Reportes:
  - diario: `python -m clwabot.core.reporter`
  - semanal: `python -c "from clwabot.core.reporter import generate_weekly_report; print(generate_weekly_report())"`

## Dashboard de urgencias

```bash
python -m clwabot.core.urgencia_dashboard --hours 24
```

## Protocolo OSCP (lab autorizado)

Guía operativa disponible en:

`docs/OSCP_LAB_PROTOCOL.md`

## Tests

```bash
python -m unittest clwabot.tests.test_urgencia_flow
python -m unittest clwabot.tests.test_meeting_flow
python -m unittest clwabot.tests.test_owner_commands_and_state
```
