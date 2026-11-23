# FASE 4 — Pipelines MVP (inventario + pedidos)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 3](fase-3-motor-etl-scheduler.md) · **Fase 4** · Siguiente → [Fase 5](fase-5-pipelines-restantes.md)

> **Continuidad.** Orquestación lista. Se implementan los primeros pipelines
> de valor alineados a HUs de inventarios y pedidos.

**Objetivo:** materializar dims de negocio necesarias + facts de inventario y
pedidos + `agg_order_kpi_daily` / `agg_inventory_kpi_daily` mínimos P0.

**Qué queda fuera:** receiving/picking completos, APIs HTTP de dashboard, tools IA.

---

## Explicación arquitectónica

Pipelines:

| Key | Extract (OLTP vía repos/ORM en infrastructure) | Load |
|-----|-----------------------------------------------|------|
| `dimensions` | facilities, references, parties, operators subset | `dim_*` |
| `inventory` | `InventoryPosition`, `InventoryMovement`, cycle counts | facts stock |
| `orders` | `Order`, lines, hitos disponibles | `fact_order*`, merge |
| `rollup_daily` | lee facts dw | `agg_*_daily` |

Contrato de hechos: respetar nombres/campos de

- `docs/hu-operative/inventories/07-indicadores-analiticas/`
- `docs/hu-operative/orders/07-indicadores-analiticas/`

Extractors viven en `core/analytics/pipelines/<name>/` e importan **repositorios
o modelos solo en infrastructure adapters**, no en domain.

## Justificación

Inventario + pedidos cubren quiebre, rotación básica, volumen, SLA/OTIF cuando
existan timestamps; son el núcleo del producto y del Assistant.

## Impacto

| Área | Cambio |
|------|--------|
| Migraciones dw facts/aggs | DDL |
| Pipelines + tests | unit con fake extract; integration opcional |
| Carga OLTP | ventanas cortas; índices ya existentes ayudan |
| Beat | activar cadencias inventory/orders/rollup |

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Hitos pedido incompletos en OLTP (`released_at`, etc.) | Cargar lo existente; campos null; no bloquear pipeline |
| Snapshot de positions costoso | Incremental `updated_at` + snapshot nightly opcional |
| Doble conteo en merge orders | Clave `(company_id, source_id)` |

## Actividades

- [ ] DDL facts/dims restantes del MVP.
- [ ] Pipeline `dimensions` completo (facility, reference, party).
- [ ] Pipeline `inventory` incremental (movements + positions).
- [ ] Pipeline `orders` incremental merge.
- [ ] Pipeline `rollup_daily` para orders + inventory P0.
- [ ] Watermark strategies documentadas por pipeline.
- [ ] Comando `analytics.reprocess` básico.
- [ ] Tests unitarios de transform (fórmulas KPI daily alineadas a HUs).
- [ ] Corrida manual en tenant de desarrollo y validación de conteos vs OLTP.

## Buenas prácticas

- Batch size acotado (ej. 1k–5k filas) por extract.
- No abrir transacciones OLTP largas; read-only / autocommit.
- Loguear `rows_extracted`, `rows_loaded`, `watermark_before/after`.

## Cómo probarlo

1. Crear movimiento de stock y pedido en tenant demo.
2. Encolar `inventory` + `orders` + `rollup_daily`.
3. Comparar `COUNT` facts vs OLTP en ventana.
4. Verificar `agg_order_kpi_daily` para el día UTC/tenant.

## Definición de Done

- [ ] Tres pipelines + rollup estables en dev.
- [ ] Reproceso por rango documentado.
- [ ] Discrepancia OLTP↔DW explicada o < umbral acordado en muestra.
