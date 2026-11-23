# FASE 7 — Madurez: LLMOps / MLOps

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 6](fase-6-integraciones-ia.md) · **Fase 7** (última)

> **Continuidad — qué se hizo en la Fase 6.** La Fase 6 usó IA generativa (cubo 1)
> para acelerar las integraciones con ERPs: mapeo de esquemas asistido por LLM,
> normalización de datos maestros y conciliación inteligente WMS ↔ ERP, siempre
> con revisión humana antes de aplicar. **La Fase 7 es transversal y continua:**
> toma todo lo desplegado (SLM/runtime de la 0b, GenAI de la 1, OR de la 2, base
> Assistant de la 3, ML de la 5 e integraciones de la 6) y lo **operativiza en
> producción** con evals, observabilidad de latencia/RAM del runtime, guardrails
> y drift. Arranca desde que hay algo en producción (tras Fase 1 / chat).

**Objetivo:** operar la IA en producción de forma sostenible: evaluación continua,
observabilidad, control de costos, seguridad y calidad. Es **transversal y
continua**, arranca desde que hay algo en producción (tras Fase 1).

**Descripción detallada:** A diferencia del software determinista, la IA se degrada
silenciosamente (drift, cambios de proveedor, prompts que dejan de funcionar,
costos que escalan). Esta fase instala las prácticas para detectarlo y controlarlo.
Cubre tanto LLMOps (para cubos 1/2) como MLOps (para cubo 3).

**Actividades:**

- [ ] **Evals** de prompts/agente: baterías con salida esperada; CI al cambiar
      prompt o versión del SLM.
- [ ] **Observabilidad**: tokens, latencia, tasa de error, y (ops) RAM/uptime del
      runtime por entorno (a partir de `usage_tracker` + métricas del contenedor).
- [ ] **FinOps de cómputo**: alertas si el runtime queda up sin uso; presupuestos
      de concurrencia; kill-switch verificado (off ⇒ proceso detenido).
- [ ] **Detección de alucinaciones y guardrails** en salidas críticas.
- [ ] **Monitoreo de drift** de modelos ML y reentrenamiento programado (Fase 5).
- [ ] **Versionado** de prompts y del tag del modelo SLM, con rollback.
- [ ] **Feature-flags / entitlements** para activar/desactivar chat e IA por
      tenant (enlaza con billing).
- [ ] **Auditoría y cumplimiento**: registro de uso de IA por tenant.
- [ ] Revisión periódica del modelo SLM (tamaño, calidad, huella RAM) y de
      adaptadores opcionales gestionados.
- [ ] Runbook de incidentes (runtime caído, cold start excesivo, salida tóxica,
      runtime olvidado encendido).

**Definición de Done de la Fase 7 (estado continuo):**

- [ ] Toda feature GenAI en producción tiene evals en CI.
- [ ] Visibilidad de uso/latencia por tenant y verificación del kill-switch de
      infra.
- [ ] Los modelos ML tienen monitoreo de drift activo.
