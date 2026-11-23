# FASE 6 — Integraciones potenciadas con IA

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 5](fase-5-ml-predictivo.md) · **Fase 6** · Siguiente → [Fase 7](fase-7-llmops-mlops.md)

> **Continuidad — qué se hizo en la Fase 5.** La Fase 5 puso en producción los
> primeros modelos predictivos del cubo 3 (p. ej. clasificación ABC y predicción
> de demanda), entrenados con el historial capturado en la Fase 4, servidos tras
> puertos (`IDemandForecaster`, etc.), versionados y con monitoreo de drift.
> **La Fase 6, en cambio, no depende de la Fase 5 ni de datos históricos:** vuelve
> al cubo 1 (GenAI) y reutiliza la tubería de las Fases 0/0b (`IChatModel` → SLM
> nativo) para atacar el dolor #1 de las integraciones con ERPs — el mapeo de
> datos. Puede ejecutarse en paralelo desde que 0/0b están listas.
>
> **Prerequisito de integraciones:** requiere al menos
> [plan-integrations Fase 2](../plan-integrations/fase-2-multitenant.md)
> (`client/features/integrations/mapping/`, conexiones tenant). Teoría en
> [plan-integrations/00-resumen-teorico.md](../plan-integrations/00-resumen-teorico.md).

**Objetivo:** usar IA generativa (cubo 1) para acelerar y robustecer las
integraciones con ERPs (SAP, SIESA), e-commerce, marketplaces y CRMs. No requiere
datos históricos.

**Descripción detallada:** El dolor #1 de las integraciones es el mapeo de datos
entre sistemas. Un LLM propone el mapeo entre los campos del sistema externo y el
modelo de datos del WMS, normaliza datos maestros sucios y explica
desalineaciones. Todo bajo revisión humana antes de aplicarse.

**Actividades:**

- [ ] **Mapeo de esquemas asistido por LLM** (`data-mapping`): dado el esquema del
      ERP externo, proponer el mapeo a nuestro modelo; revisión y aprobación
      humana antes de activar.
- [ ] **Normalización de datos maestros** (`product-sync`, terceros): deduplicar y
      limpiar referencias/terceros que llegan sucios del ERP.
- [ ] **Conciliación inteligente** (`inventory-sync`, `order-sync`): detectar
      desalineación entre nuestro estado y el del ERP y explicar la causa probable.
- [ ] Integrar con [plan-integrations](../plan-integrations/00-resumen-teorico.md):
      `SuggestOrderMappingUseCase` lee `FieldMapping` y propone reglas vía
      `core/ai`; UI en [Fase 5 integraciones](../plan-integrations/fase-5-client-web.md)
      (`mapping-editor`); guardrails human-in-the-loop antes de activar.
- [ ] Conciliación inteligente reutiliza `ConflictResolver` (WMS_WINS) y enriquece
      el `SyncResult.warnings` con explicación LLM (`integrations.order-sync`).
- [ ] Guardrails: ningún mapeo o normalización se aplica sin aprobación humana.
- [ ] Tests.

**Definición de Done de la Fase 6:**

- [ ] Al menos el mapeo asistido de un ERP real funciona con revisión humana.
