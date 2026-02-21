```text
                 _-::::::--_
              ,d$$$$$$$$$$$SIIi:.
           ,s$$$$$$$$$$$$$$$SIII::.
         jI$$$$$$$$$$$$$$$$SSISSi:.
       ,s$$$$$$$$$$$$$$$$$$$$$$$Ii:
      j~?$$$$$$$$$$$$$$$$$$$$$$$$Ii
      :   ?$$$$$$$$$$$$$   $$$$$$I:
      j_ /$$7`°4$$$$$7    $$$$$$$I'
      º?º"7$$:    `$k  :i$$$$$$$7'
         i  ?$L,   ,d$     $$$7'
        ,d. J$$$$$$$$SL, .'$$
       ?$$$$$$$k:7$$º,   °,'
       `..ººº^' :jIS7
       j$k,i;/_,oSSI'
       ?SS$$$$$$7º
        `ººººº"`                 skull mode
```

# ares_mers_agent // skull mode

Automatizacion local de WhatsApp sobre OpenClaw, con flujos de:

- urgencias VIP (protocolo 1-4)
- agenda de reuniones para contactos externos
- reglas de presencia owner y respuesta natural
- generacion de eventos `.ics`
- metricas y reportes

## Estructura del Craneo

- `clwabot/core/`: lógica de negocio (routing, urgencias, reuniones, estado, reporter)
- `clwabot/hooks/`: integración runtime con logs/gateway
- `clwabot/config/`: contactos y guiones
- `clwabot/data/`: estado persistente y reportes
- `clwabot/tests/`: tests unitarios y de flujo

## Arranque Runtime (24/7) - Pulso Vital

Router unificado:

```bash
openclaw logs --follow | python3 -m clwabot.hooks.whatsapp_router_watch
```

Servicio systemd user (recomendado):

```bash
systemctl --user status clwabot-router.service
systemctl --user restart clwabot-router.service
journalctl --user -u clwabot-router.service -f
```

## Flujos Principales

### Urgencias VIP - Alerta Roja

- Trigger: `urgente` / `urgencia`
- Catálogo:
1. Evento
2. Nota
3. Recordatorio
4. Inmediata
- Confirmación, cierre, alerta al owner, `.ics` cuando aplica.

### Reuniones (externos) - Protocolo Agenda

- Trigger: intención de reunión (`agendar`, `reunión`, `meeting`, etc.)
- Formulario guiado: tema, fecha, hora, duración, modalidad.
- Confirmación final + `.ics`.
- Gate anti-robot: espera 15s y evita disparar si detecta actividad owner.

## Comandos Owner (por WhatsApp)

- `/status`
- `/pausar`, `/reanudar`
- `/modo normal|busy|vacation`
- `/horario HH:MM HH:MM`
- `/forzar-reunion +MSISDN`
- `/ayuda`

## Reportes y Mantenimiento

```bash
python3 -m clwabot.core.reporter
python3 -c "from clwabot.core.reporter import generate_weekly_report; print(generate_weekly_report())"
python3 -m clwabot.core.maintenance
```

## Tests (Sanity Check)

```bash
python3 -m unittest discover -s clwabot/tests -p "test_*.py"
```
