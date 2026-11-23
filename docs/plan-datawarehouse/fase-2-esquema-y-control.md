# FASE 2 — Esquema dimensional + control plane

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 1](fase-1-capa-transversal.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-motor-etl-scheduler.md)

> **Continuidad.** Con puertos listos, materializamos el **esqueleto vacío** de
> `ctl` / `stg` / `dw` en `wadw` y el adaptador Postgres real para DDL/DML básico.

**Objetivo:** schemas versionados, tablas de control (watermarks, runs) y
dimensiones mínimas (`dim_date`, `dim_company`) sin aún llenar facts de
inventario/pedidos.

**Qué queda fuera:** extractors warehouse, Beat fan-out, APIs KPI.

---

## Explicación arquitectónica

App Django (SHARED, **router → analytics DB**):

`platform.features.analytics.control.ctl` (`label=analytics_ctl`)

- Modelos de control mapean a `ctl.*` / `dw.*` (`managed=False`).
- Tablas creadas vía migraciones RunSQL **solo DDL** — **prohibido** insertar
  catálogos de negocio.
- `dim_date`: management command `load_dim_date --from --to` (seed operativo,
  no migration).
- Migrar wadw: `python manage.py migrate_analytics` (no `migrate --database=…`:
  django-tenants intercepta `migrate`).

`PostgresAnalyticsStore` usa `connections['analytics']`.

## Justificación

- Control plane en wadw (no en OLTP) para no mezclar retención.
- `dim_date` y `dim_company` desbloquean joins de todos los facts posteriores.
- Separar DDL de seed respeta la regla del repo.

## Impacto

| Área | Cambio |
|------|--------|
| `INSTALLED_APPS` / SHARED_APPS | App analytics control |
| `migrate_analytics` | Schemas + tablas en wadw |
| Comandos | `load_dim_date`, `sync_dim_company` |
| Router | Label `analytics_ctl` |

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Migrar accidentalmente a `default` | Router `allow_migrate`; CI/docs |
| `migrate --database=analytics` marca todas las apps | Comando `migrate_analytics` solo `analytics_ctl` |
| SCD prematuro en todas las dims | Solo company/date en esta fase; resto en pipelines |

## Modelo mínimo `ctl`

- `pipeline_watermarks (company_id, pipeline_key, cursor_*, strategy, updated_at)`
- `pipeline_runs (...)`
- `pipeline_run_steps (...)`

## Modelo mínimo `dw`

- `dim_date`
- `dim_company`

## Actividades

- [x] Crear app + modelos control / migraciones DDL.
- [x] Crear schemas SQL `ctl`, `stg`, `dw`.
- [x] Cablear `PostgresAnalyticsStore` (upsert dim company/date, insert run).
- [x] Command `load_dim_date`.
- [x] Command o use case `sync_dim_company` leyendo `Company` en public (sin tenant loop).
- [x] Tests unitarios dim_date builder + router labels (integration manual contra wadw).

## Buenas prácticas

- `managed = False` con DDL RunSQL en schemas dedicados.
- Índices únicos `(company_id, pipeline_key)` en watermarks.

## Cómo probarlo

```bash
python manage.py migrate_analytics
python manage.py load_dim_date --from 2024-01-01 --to 2030-12-31
python manage.py sync_dim_company
python manage.py shell -c "from django.db import connections; c=connections['analytics'].cursor(); c.execute('select count(*) from dw.dim_date'); print(c.fetchone())"
```

## Definición de Done

- [x] Migraciones analytics aplican en limpio.
- [x] `dim_date` poblable por comando.
- [x] Watermark/run pueden insertarse vía store.
- [x] Cero facts de negocio cargados.
