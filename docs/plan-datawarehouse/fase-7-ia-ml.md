# FASE 7 — Tools assistant + export ML-ready

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 6](fase-6-apis-consumo.md) · **Fase 7**

> **Acoplamiento:** [plan-ia Fase 3](../plan-ia/fase-3-copiloto-agentico.md),
> [Fase 4 instrumentación](../plan-ia/fase-4-instrumentacion-datos.md),
> [Fase 5 ML](../plan-ia/fase-5-ml-predictivo.md).

**Objetivo:** que el copiloto consulte históricos/KPIs vía tools sobre use cases
analytics, y que exista un export por tenant para entrenamiento (cubo 3).

## Explicación

- Registrar tools (`get_order_kpis`, `get_inventory_snapshot_metrics`, …) que
  invocan los mismos use cases de Fase 6 (DRY, mismos guardrails de tenant).
- **Prohibido** en MVP: SQL generado por el LLM contra wadw.
- Export ML-ready: comando/task que materializa dataset (CSV/Parquet en MinIO
  o vista `ml.*`) filtrado por `company_id`, best-effort, sin hot path.

## Actividades

- [ ] Tools Assistant + tests de aislamiento.
- [ ] Documentar catálogo de preguntas soportadas (OTIF, quiebre, volumen…).
- [ ] Job `analytics.export_ml_dataset`.
- [ ] Checklist de columnas alineada a plan-ia Fase 4.
- [ ] Verificar kill-switch: si `ANALYTICS_ENABLED=false`, tools degradan mensaje.

## Definición de Done

- [ ] Assistant responde KPI de demo con dato proveniente de wadw.
- [ ] Export ML generable por tenant sin mezclar empresas.
- [ ] Enlace explícito actualizado en bitácoras de plan-ia / este plan.
