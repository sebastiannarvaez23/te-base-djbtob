# FASE 3 — Motor ETL + scheduler Celery

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 2](fase-2-esquema-y-control.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-pipelines-mvp.md)

> **Continuidad.** El store Postgres y `ctl` existen. Ahora el **transporte**
> Celery orquesta pipelines (aún puede ser un pipeline `smoke` / dims-only).

**Objetivo:** tasks de orquestación + per-tenant, locks, registro en
`ctl.pipeline_runs` y visibilidad en `task_monitor`, entradas Beat.

**Qué queda fuera:** extractors reales de inventory/orders (Fase 4).

---

## Explicación arquitectónica

```
Beat: analytics.orchestrate-<pipeline>
  └─ BaseTask  list_companies()
       └─ apply_async TenantTask analytics.run_pipeline
            kwargs: schema_name, company_id, pipeline_key
                 └─ redis_lock(analytics:{pipeline}:{schema})
                      └─ track_task_run(...)
                           └─ PipelineRunner.run(ctx)
                                └─ actualiza watermark + ctl.pipeline_runs
```

Reutilizar:

- `TenantTask`, `redis_lock`, `track_task_run`
- Extender `TASK_CATALOG` y `build_beat_schedule`

Pipeline `dimensions` (sync company + noop) como smoke end-to-end.

## Justificación

Un solo bus de tareas = misma ops, mismos incidentes, misma UI admin. El
detalle granular (rows, watermark) vive en `ctl`; el overbook Celery en
task_monitor.

## Impacto

| Área | Cambio |
|------|--------|
| `core/analytics/tasks/` | orchestrate + run |
| `core/tasks/schedules.py` | entradas analytics |
| `task_monitor/domain/catalog.py` | defs |
| Workers | Documentar cola opcional `analytics` |

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Fan-out masivo satura workers | Rate limit / chunk; cadencias suaves al inicio |
| Lock TTL < runtime | TTL > soft_time_limit; token ownership ya en `redis_lock` |
| Beat backlog | `options.expires` obligatorio |

## Actividades

- [ ] Task `analytics.run_pipeline` (`TenantTask`).
- [ ] Task `analytics.orchestrate_pipeline` (public) con filtro opcional de company_ids.
- [ ] Integrar `PipelineRunner` + persistencia de run/steps/watermark.
- [ ] Pipeline smoke `dimensions` registrado.
- [ ] Beat entries (pueden quedar disabled por setting `ANALYTICS_BEAT_ENABLED`).
- [ ] Catálogo task_monitor.
- [ ] Tests: lock skip, schema_context wrap (patrón `core/tests/test_tenant_task.py`).

## Buenas prácticas

- Nombres `analytics.<verb>` coherentes con onboarding/subscription.
- Idempotencia: mismo watermark ⇒ extract vacío ⇒ success `rows=0`.
- No calcular KPIs aquí.

## Cómo probarlo

```bash
celery -A base worker -l info
celery -A base beat -l info
# Encolar manual
python manage.py shell -c "from core.analytics.tasks import run_pipeline; run_pipeline.apply_async(kwargs={'schema_name':'…','company_id':'…','pipeline_key':'dimensions'})"
# Verificar ctl.pipeline_runs + UI task_monitor
```

## Definición de Done

- [ ] Fan-out + run tenant funcionan con pipeline `dimensions`.
- [ ] Runs visibles en `ctl` y task_monitor.
- [ ] Setting para apagar Beat analytics sin apagar el resto.
