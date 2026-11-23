# FASE 5 — Pipelines restantes + rollups

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 4](fase-4-pipelines-mvp.md) · **Fase 5** · Siguiente → [Fase 6](fase-6-apis-consumo.md)

**Objetivo:** añadir `receiving`, `picking`, `operations` y rollups asociados;
dejar **stubs versionados** para `packing`, `dispatch`, `returns` cuando el
OLTP exista.

## Explicación

Misma mecánica que Fase 4. Fuentes:

- Receiving: `Receipt`, `ReceiptLine`, `PutawayTask`, deliveries
- Picking: `PickTask`
- Operations: `Transfer`, `CycleCount`

Consultar catálogos HU de receiving/inventories para hechos mínimos.

## Actividades

- [ ] Pipeline `receiving` + facts + watermark.
- [ ] Pipeline `picking` + `agg_picking_kpi_daily`.
- [ ] Pipeline `operations`.
- [ ] Registrar stubs `packing`/`dispatch`/`returns` que fallen con
      `PipelineNotReady` hasta existir modelos.
- [ ] Ajustar cadencias Beat.
- [ ] Tests transform + una integration por pipeline.

## Riesgos

- Módulos OLTP en evolución → versionar schemas de staging.
- Productividad operario depende de `assigned_to` poblado.

## Definición de Done

- [ ] Pipelines P1 en verde en tenant demo.
- [ ] Stubs explícitos para módulos no existentes (no silenciosos).
