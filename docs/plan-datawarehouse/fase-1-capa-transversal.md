# FASE 1 — Capa transversal (`core/analytics/`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 0](fase-0-cimientos.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-esquema-y-control.md)

> **Continuidad.** Fase 0 dejó el alias `analytics` vivo. Esta fase clona el
> patrón de `core/integrations/` / `core/ai/`: **puertos + fake + facade**, sin
> persistencia dimensional real.

**Objetivo:** que cualquier feature futura pueda orquestar un pipeline y
leer/escribir el store vía contratos, con tests unitarios offline
(`FakeAnalyticsStore`).

**Qué queda fuera:** migraciones `ctl`/`dw`, Beat, pipelines reales de warehouse.

---

## Explicación arquitectónica

```
core/analytics/
├── __init__.py              # facade: get_analytics_store, run_pipeline
├── config.py                # settings ANALYTICS_*
├── domain/
│   ├── interfaces.py        # IAnalyticsStore, IPipeline, IExtractor, ITransformer, ILoader
│   ├── schemas.py           # PipelineContext, PipelineResult, AnalyticsQuery, Watermark
│   └── enums.py             # PipelineKey, RunStatus, Trigger, WatermarkStrategy
├── application/
│   ├── pipeline_runner.py   # extract → stage → transform → load + métricas
│   └── query_service.py     # lecturas tipadas (stubs)
├── infrastructure/
│   ├── fake_store.py
│   ├── postgres_store.py    # esqueleto; puede no-op hasta Fase 2
│   └── registry.py          # pipeline_key → IPipeline
├── pipelines/
│   └── __init__.py          # vacío / NullPipeline para tests
└── observability/
    └── metrics.py           # contadores simples (rows, duration)
```

## Justificación

- El resto del mono **no** dependerá de SQL de Postgres-DW ni de ClickHouse.
- `execute_transform` en el puerto prepara ELT sin usarlo aún.
- Tests `pytest -m unit` sin Docker DW (fake).

## Impacto

| Área | Cambio |
|------|--------|
| `core/analytics/` | Paquete nuevo |
| Settings | `ANALYTICS_ENABLED`, `ANALYTICS_STORE=fake|postgres` |
| Tests | `core/tests/unit/analytics/` |
| CLAUDE.md (opcional) | Mención breve del módulo (solo si el equipo lo pide en la fase) |

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Sobreingeniería de interfaces | Limitar a los puertos del resumen; no event-sourcing |
| PostgresStore prematuro | Implementar métodos mínimos; raise `NotImplemented` en transforms ELT |

## Actividades

- [x] Crear estructura de carpetas y facade pública.
- [x] Definir schemas Pydantic de contexto/resultado/query/watermark.
- [x] Implementar `FakeAnalyticsStore` in-memory.
- [x] Implementar `PipelineRunner` con pasos medidos (sin Celery).
- [x] Registry de pipelines + `NullPipeline` de prueba.
- [x] Unit tests: runner feliz, fallo en transform no llama load, query fake.
- [x] Documentar uso mínimo en docstring del package (como `core/ai`).

## Buenas prácticas

- Dependencia: application → domain; infrastructure → domain.
- No importar modelos Django warehouse desde `domain/`.
- Errores: familia de códigos `ANL_xxx` en `core/errors` solo si se exponen a API; si no, excepciones internas tipadas.

## Cómo probarlo

```bash
pytest core/tests/unit/analytics/ -m unit -q
```

## Definición de Done

- [x] Facade importable: `from core.analytics import get_analytics_store, run_pipeline`.
- [x] Suite unitaria verde con store fake.
- [x] `ANALYTICS_STORE=fake` por defecto en tests / safe default.
