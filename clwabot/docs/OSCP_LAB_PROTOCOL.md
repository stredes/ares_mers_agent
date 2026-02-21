# Protocolo OSCP-Style para Laboratorio Autorizado

## 1. Marco de autorización (obligatorio)
- Propietario del entorno: `stredes`.
- Alcance permitido: red local de laboratorio y páginas de prueba diseñadas por ti.
- Base contractual: formación/pentest autorizado (OSCP / contrato IBM).
- Exclusiones: activos de terceros, servicios productivos, datos personales reales.

## 2. Rules of Engagement (RoE)
- Ventana de pruebas: definir horario (`HH:MM-HH:MM`).
- Máximo impacto permitido: sin DoS, sin cifrado destructivo, sin borrado de datos.
- Cuentas de prueba: usar credenciales de laboratorio.
- Registro obligatorio: toda acción debe tener evidencia (comando, hora, resultado).
- Criterio de parada: si hay inestabilidad no esperada, detener y documentar.

## 3. Fases del ejercicio

### Fase A: Preparación
- Inventario de objetivos (IP, hostname, URL, rol).
- Clasificación: Linux / Windows / AD / Web.
- Verificar backups/snapshots del lab.
- Crear carpeta de evidencias por fecha.

### Fase B: Enumeración
- Descubrir superficie expuesta de forma controlada.
- Identificar servicios/versiones y rutas de ataque probables.
- Priorizar por riesgo y facilidad de validación.
- Documentar falsos positivos y hallazgos potenciales.

### Fase C: Validación de hallazgos
- Confirmar vulnerabilidades solo en entorno autorizado.
- Demostrar impacto mínimo necesario (PoC controlada).
- No usar técnicas de persistencia destructiva.
- Registrar evidencia reproducible paso a paso.

### Fase D: Post-explotación ética (limitada)
- Verificar alcance de acceso conseguido.
- Validar segmentación, privilegios y exposición de secretos de prueba.
- No extraer datos sensibles reales.
- Cerrar sesión y limpiar artefactos creados para la prueba.

### Fase E: Remediación y re-test
- Proponer fix técnico y compensaciones temporales.
- Re-ejecutar prueba para validar cierre.
- Marcar estado: `open`, `mitigated`, `closed`.

## 4. Evidencia mínima por hallazgo
- ID de hallazgo.
- Activo afectado.
- Severidad (Crítica/Alta/Media/Baja).
- Condición observada.
- Impacto real en el negocio/lab.
- Evidencia (capturas, logs, salida de comandos).
- Recomendación concreta.
- Resultado de re-test.

## 5. Plantilla de reporte técnico

## Resumen ejecutivo
- Objetivo del ejercicio
- Riesgo general observado
- Top 3 hallazgos

## Hallazgos
Para cada hallazgo:
- Título
- Severidad
- Activo
- Evidencia
- Impacto
- Recomendación
- Estado

## Plan de acción
- 24h: controles rápidos
- 7 días: correcciones prioritarias
- 30 días: hardening y monitoreo continuo

## 6. Checklist operativo diario
- [ ] Alcance confirmado
- [ ] Objetivos vivos y estables
- [ ] Evidencias guardadas
- [ ] Hallazgos priorizados
- [ ] Recomendaciones redactadas
- [ ] Re-test parcial ejecutado

## 7. Checklist de hardening posterior
- [ ] Parcheo SO y servicios
- [ ] Mínimo privilegio en cuentas
- [ ] MFA donde aplique
- [ ] Segmentación de red
- [ ] Secretos rotados
- [ ] Logging central y alertas
- [ ] Backup y restore probado

## 8. Integración sugerida con tu agente
Comandos recomendados para operar este protocolo por WhatsApp:
- `/oscp-status`
- `/oscp-plan`
- `/oscp-next`
- `/oscp-labs`
- `/oscp-lab <nombre> <pending|in_progress|rooted>`
- `/oscp-note <lab> | <nota>`

## 9. Límite ético/legal permanente
Si una acción no está explícitamente autorizada por alcance y contrato, no se ejecuta.
