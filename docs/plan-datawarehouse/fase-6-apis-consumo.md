# FASE 6 — APIs de consumo (dashboards / KPIs)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 5](fase-5-pipelines-restantes.md) · **Fase 6** · Siguiente → [Fase 7](fase-7-ia-ml.md)

**Objetivo:** exponer lecturas tipadas desde wadw para `base-client-web`
(dashboards / strips avanzados) sin tocar el hot path OLTP.

## Explicación

Feature sugerida: `client/features/analytics/` (TENANT_APPS **solo** para
presentation/authz context; **datos** vía `IAnalyticsStore`, no modelos tenant).

```
presentation (RequestBody/QueryFilter)
  → use cases (GetOrderKpis, GetInventoryKpis, GetTimeseries)
      → IAnalyticsStore.query(AnalyticsQuery)
```

Admin opcional: agregados multi-tenant **sin** PII (conteos plataforma).

## Fronteras

- Strip liviano en pantallas operativas puede seguir temporalmente en OLTP;
  migrar a aggs cuando estén calientes.
- Export reportes: job Celery + archivo MinIO (reutilizar `core/storage`).
- Entitlements: declarar features; **no cablear** aún (mocks).

## Actividades

- [ ] Schemas de respuesta KPI alineados a HUs P0.
- [ ] Endpoints `api/v1/analytics/...` con QueryFilter (periodo, facility).
- [ ] Forzar `company_id` desde tenant context.
- [ ] Tests API: aislamiento cross-tenant.
- [ ] Documentar contrato para Angular (sin implementar UI aquí salvo acuerdo).

## Definición de Done

- [ ] Al menos KPIs P0 orders + inventory consultables por API.
- [ ] Test de aislamiento tenant verde.
- [ ] Ningún endpoint acepta `company_id` libre del cliente.
