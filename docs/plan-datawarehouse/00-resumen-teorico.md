# Plan de Trabajo Data Warehouse — Resumen teórico (base)

> **Propósito de este documento.** Hoja de ruta única para construir el **Data
> Warehouse empresarial (wadw)** de BASE: extracción, transformación, carga,
> pipelines incrementales, observabilidad, dashboards/KPIs y consumo por base
> Assistant / ML. Está escrito para que cualquier colega del equipo entienda
> qué se construye, por qué, en qué orden y cómo encaja en la arquitectura
> hexagonal multi-tenant ya existente — **sin soluciones genéricas**.
>
> **Cómo se usa.** Este archivo contiene la parte **teórica** (auditoría del
> estado actual, glosario, fronteras, arquitectura objetivo, modelo dimensional,
> multi-tenant, ETL→ELT, mapa de fases). Cada fase de construcción vive en su
> propio archivo dentro de `docs/plan-datawarehouse/`. Marca `[x]` cuando una
> actividad esté **terminada y verificada**. No marques algo "a medias".
>
> **Regla de trabajo.** No se implementa la siguiente fase hasta cerrar la
> anterior (DoD). No se escribe código de pipelines de negocio en Fase 0–1.

---

## Índice

### Teoría (este archivo)

1. [Auditoría del estado actual](#1-auditoría-del-estado-actual)
2. [Contexto y objetivo](#2-contexto-y-objetivo)
3. [Glosario](#3-glosario)
4. [Fronteras con capas existentes](#4-fronteras-con-capas-existentes)
5. [Principios de arquitectura](#5-principios-de-arquitectura)
6. [Diseño del Data Warehouse (wadw)](#6-diseño-del-data-warehouse-wadw)
7. [Motor ETL (y preparación ELT)](#7-motor-etl-y-preparación-elt)
8. [Multi-tenant en analítica](#8-multi-tenant-en-analítica)
9. [Pipelines independientes](#9-pipelines-independientes)
10. [Procesamiento incremental](#10-procesamiento-incremental)
11. [Scheduler (Celery + RedBeat)](#11-scheduler-celery--redbeat)
12. [Observabilidad](#12-observabilidad)
13. [Dashboards, KPIs y reportes](#13-dashboards-kpis-y-reportes)
14. [assistant e IA](#14-assistant-e-ia)
15. [Acoplamiento con otros planes](#15-acoplamiento-con-otros-planes)
16. [Mapa de fases](#16-mapa-de-fases)
17. [Bitácora de decisiones](#17-bitácora-de-decisiones)

### Fases de construcción

- [FASE 0 — Cimientos (DB wadw + settings + router)](fase-0-cimientos.md)
- [FASE 1 — Capa transversal (`core/analytics/`)](fase-1-capa-transversal.md)
- [FASE 2 — Esquema dimensional + control plane](fase-2-esquema-y-control.md)
- [FASE 3 — Motor ETL + scheduler Celery](fase-3-motor-etl-scheduler.md)
- [FASE 4 — Pipelines MVP (inventario + pedidos)](fase-4-pipelines-mvp.md)
- [FASE 5 — Pipelines restantes + rollups diarios](fase-5-pipelines-restantes.md)
- [FASE 6 — APIs de consumo (dashboards / KPIs)](fase-6-apis-consumo.md)
- [FASE 7 — Tools assistant + export ML-ready](fase-7-ia-ml.md)

---

## 1. Auditoría del estado actual

Análisis realizado sobre el código de `base` **antes** de proponer
implementación. Conclusiones ancladas a rutas reales.

### 1.1 Cómo está construido el proyecto

| Capa | Qué es | Dónde |
|------|--------|-------|
| Config Django | Settings jerárquicos, tenants, Celery, Redis, MinIO, AI | `base/settings/` |
| Mundo plataforma | Schema `public`: company, billing, support, flags… | `platform/features/` |
| Mundo tenant | Schema por empresa: warehouse, logging, integrations, assistant… | `client/features/` |
| Transversal | Errores, audit, tasks, AI, storage, integrations, access, flags | `core/` |
| Hexagonal por feature | `domain/` → `application/` → `infrastructure/` → `presentation/` | Cada feature |
| Multi-tenant | django-tenants; `TENANT_MODEL = company.Company` | `base/settings/base.py` |
| OLTP | Una sola entrada `DATABASES['default']` → PostgreSQL `wadb` | `base/settings/local.py` |
| Colas | Celery + Redis broker DB/2 + RedBeat DB/3 | `core/tasks/`, `base/celery.py` |
| Monitor de tareas | Runs/steps en schema público | `platform/features/support/task_monitor/` |
| IA | Puertos `core/ai/`; chat en `client/features/assistant/` | plan-ia |
| Integraciones | Puertos `core/integrations/`; sync orders con `TenantTask` | plan-integrations |

**Warehouse operativo ya presente (TENANT_APPS):**

- `inventory.reference`, `inventory.balances`, `inventory.stock`
- `facilities`, `foundation`, `receiving`, `orders`, `picking`, `operations`
- `third_parties`, `integrations`, `assistant`, logging tenant

**Aún no existen como módulos de dominio maduros:** packing dedicado,
despacho/dispatch formal, devoluciones — parcialmente anticipados en HUs y
catálogos de indicadores (`docs/hu-operative/`).

### 1.2 Patrones arquitectónicos en uso

1. **Monolito modular** + Clean Architecture por feature.
2. **Puertos y adaptadores** en módulos transversales (`core/ai`,
   `core/storage`, `core/integrations`) — el use case depende del puerto, no
   del proveedor.
3. **Validación HTTP** con `RequestBody` / `QueryFilter` (no serializers DRF
   de input).
4. **Salida** con schemas Pydantic + `wrap_response()`.
5. **Celery como transporte único** de trabajo asíncrono:
   - `BaseTask` — retries solo transitorios, logging, incidentes.
   - `TenantTask` — `schema_name` + `schema_context`.
   - `redis_lock` — exclusión mutua.
   - `TaskRunContext` / `track_task_run` — pasos + compensación LIFO.
   - Beat estático vía `build_beat_schedule()` + RedBeat.
6. **Best-effort** en infra auxiliar (Redis caído, IA, incidentes): el hot path
   WMS no se rompe.
7. **Features catalog + entitlements** (`core/access`) — cableado de permisos
   diferido en módulos operativos según reglas del repo.

### 1.3 Fortalezas a aprovechar

- Infra de tareas **ya lista** para fan-out por tenant (`TenantTask`, locks,
  Beat, monitor).
- Patrón transversal probado (`core/integrations` es el gemelo más cercano a
  un motor ETL: runner, resiliencia, observabilidad, fake para tests).
- Catálogos de **KPIs y hechos mínimos** ya documentados en HUs
  (`docs/hu-operative/*/07-indicadores-analiticas/`) — no inventar métricas
  desde cero.
- Plan IA Fase 4 (`instrumentación ML-ready`) y Fase 5 (predictivo) **exigen**
  historial — el DW es el destino natural.
- Modelos warehouse con UUID PK, timestamps y movimientos idempotentes
  (`InventoryMovement.idempotency_key`) — buenos candidatos a watermark.

### 1.4 Problemas / gaps observados

| Gap | Impacto |
|-----|---------|
| **No existe `wadw`** en `docker-compose.yml` ni en `DATABASES` | Hay que crear la segunda base y el wiring |
| **No hay multi-DB router propio** (solo `TenantSyncRouter`) | OLTP y DW deben separarse con router explícito |
| **Analítica vive solo en docs HUs** — cero código `analytics` | Hay que crear capa sin contaminar hot path |
| Packing / dispatch / returns incompletos en código | Pipelines se versionan; MVP = inventario + pedidos (+ receiving/picking) |
| Riesgo de calcular KPIs en request HTTP | Los catálogos ya lo prohíben; el DW refuerza esa frontera |
| Mezclar hechos en schemas tenant OLTP | Inflaría backups/retención operativa; wadw debe ser destino |

### 1.5 Qué reutilizar (obligatorio)

| Existente | Uso en DW |
|-----------|-----------|
| `core.tasks.base.TenantTask` | Ejecutar extract por tenant |
| `core.tasks.base.BaseTask` + `redis_lock` | Orquestadores, exclusiones |
| `core.tasks.run_context.track_task_run` | Pasos visibles en task_monitor |
| `core.tasks.schedules.build_beat_schedule` | Cadencias de pipelines |
| `platform…task_monitor` | Catálogo + UI admin de runs Celery |
| Repositorios / interfaces warehouse | Lectura OLTP vía puertos (no SQL crudo ad hoc en use cases) |
| `core/errors`, logging `app.tasks` | Errores y traza |
| Catálogos HU indicadores | Diccionario de hechos/dims |
| Patrón `core/integrations` | Plantilla de `core/analytics` |

### 1.6 Qué no modificar (salvo necesidad explícita)

- Modelos OLTP de warehouse (no añadir columnas “solo para analytics” si se
  puede derivar; instrumentación de timestamps canónicos sí puede pedirse vía
  HUs operativas, no vía el plan DW).
- `TenantTask` / contrato `schema_name` (extender, no reescribir).
- django-tenants en `default` (el DW **no** usa schema-per-tenant en wadw).
- Hot path de APIs operativas (recibir, pick, reservar): **cero** escritura
  síncrona al DW en el request.
- Semillas en migraciones (regla del repo).

### 1.7 Componentes nuevos a crear

| Componente | Ubicación propuesta |
|------------|---------------------|
| DB PostgreSQL `wadw` | Compose + settings `DATABASES['analytics']` |
| Router multi-DB | `core/analytics/infrastructure/db_router.py` |
| Capa transversal ETL/DW | `core/analytics/` |
| Control plane (watermarks, pipeline runs) | Schema `ctl` en wadw (+ app Django ligera) |
| Staging + marts dimensionales | Schemas `stg` / `dw` en wadw |
| Pipelines por dominio | `core/analytics/pipelines/<name>/` |
| Orquestación Celery | `core/analytics/tasks/` + entradas Beat |
| APIs de lectura KPI/dashboard | `client/features/analytics/` (tenant) y opcional admin |
| Tools Assistant / export ML | Fase 7; enlaza plan-ia |

---

## 2. Contexto y objetivo

**Objetivo:** que BASE tenga una **plataforma analítica** propia, barata de
operar, alineada al monolito, que sirva de fuente de verdad **histórica y
agregada** para:

- Dashboards e indicadores (catálogos eje 5/6 de HUs)
- Reportes
- assistant (tendencias, KPIs, históricos)
- ML predictivo (plan-ia Fase 5)
- Analítica de plataforma (admin) sin mezclar datos de empresas en respuestas
  de cliente

**No-objetivos (esta hoja de ruta no hace):**

- Sustituir el OLTP ni consultar el DW para transacciones de piso.
- Adoptar Spark/Airflow/dbt Cloud/Kafka en el MVP (sobreingeniería).
- ClickHouse en Fase 0–5 (solo **puertos** listos para sustituir el adaptador).
- Cablear entitlements `analytics.*` hasta el pase final de permisos (regla
  del repo); dejar mocks/comentarios si hace falta.
- Cubos OLAP ad-hoc completos en el MVP (Fase 6 entrega lecturas KPI + series;
  OLAP rico es evolución).

---

## 3. Glosario

| Concepto | Qué es | Dónde vive |
|----------|--------|------------|
| **OLTP (`wadb`)** | BD transaccional multi-schema (django-tenants) | `DATABASES['default']` |
| **DW (`wadw`)** | BD analítica dedicada | `DATABASES['analytics']` |
| **Pipeline** | Unidad ETL desacoplada (ej. `inventory`, `orders`) | `core/analytics/pipelines/` |
| **Watermark** | Cursor incremental (ts / id / versión) por tenant+pipeline | `ctl.pipeline_watermarks` |
| **Run** | Una ejecución de pipeline (tenant o lote) | `ctl.pipeline_runs` (+ opcional task_monitor) |
| **Staging (`stg`)** | Copia cruda/ligeramente tipada del extract | Schema `stg` en wadw |
| **Mart (`dw`)** | Star schema: dims + facts + rollups | Schema `dw` en wadw |
| **Control (`ctl`)** | Metadatos de orquestación | Schema `ctl` en wadw |
| **Tenant key** | Identidad estable de empresa en el DW (`company_id` UUID) | Columna en toda fila de negocio |
| **Extractor** | Lee OLTP (vía repo/SQL acotado) | Puerto `IExtractor` |
| **Transformer** | Normaliza a filas de hechos/dims | Puerto `ITransformer` |
| **Loader** | Upsert/insert en wadw | Puerto `ILoader` / `IAnalyticsStore` |
| **Analytics store** | Motor físico (Postgres hoy; ClickHouse mañana) | Adaptador tras `IAnalyticsStore` |

---

## 4. Fronteras con capas existentes

```
Request operativo WMS
  └─► use case warehouse (OLTP) ──✗── no escribe DW

Celery Beat / manual
  └─► orchestrator (core/analytics)
        ├─► TenantTask(schema_name)  → extract OLTP
        ├─► transform (CPU, sin OLTP lock largo)
        └─► load → wadw (IAnalyticsStore)

Request dashboard / Assistant tool
  └─► use case analytics (solo lectura)
        └─► IAnalyticsStore.query(...)  filtrado por company_id
```

| Capa existente | Relación |
|----------------|----------|
| `core/tasks` | Transporte y tenant context; **no** reimplementar Cola |
| `task_monitor` | Observabilidad de la tarea Celery; detalle ETL fino en `ctl.*` |
| `client/features/logging` | Eventos operativos OLTP; **no** sustituyen el DW |
| `core/ai` + Assistant | Consumidores de lecturas agregadas (Fase 7) |
| `core/integrations` | Patrón a clonar; sync ERP ≠ ETL analítico |
| HUs indicadores | Diccionario de métricas; el DW materializa hechos |
| `core/access` / flags | Diferido; diseño de features `analytics.*` sí se documenta |

---

## 5. Principios de arquitectura

1. **Misma filosofía que `core/ai` y `core/integrations`:** puertos en domain,
   adaptadores en infrastructure, facade pública estable.
2. **El resto del sistema no conoce PostgreSQL-DW ni ClickHouse** — solo
   `IAnalyticsStore` y schemas de consulta.
3. **Pipelines independientes** — fallo de `picking` no bloquea `inventory`.
4. **Incremental por defecto; full refresh explícito** (reproceso).
5. **Aislamiento de tenant por `company_id`** en wadw (no schema-per-tenant).
6. **Bajo costo:** un Postgres adicional (mismo host en dev; instancia
   separable en prod), sin cluster nuevo.
7. **KISS:** Python + SQL + Celery; nada de orquestadores externos en MVP.
8. **Testeable:** `FakeAnalyticsStore`, pipelines con extractors fake.
9. **Sin seed en migraciones** del DW (schema vacío; datos solo por ETL).

---

## 6. Diseño del Data Warehouse (wadw)

### 6.1 Topología física

**Dev (bajo costo):** segundo database en el mismo contenedor Postgres
(`POSTGRES_MULTIPLE_DATABASES` o `CREATE DATABASE wadw`), puerto único.

**Prod (recomendado a medio plazo):** instancia Postgres separada
(IOPS/backup/retention distintos del OLTP). Misma conexión lógica
`DATABASES['analytics']`.

```
docker-compose (evolución Fase 0)
  postgres     → wadb (OLTP, schemas tenant)
  postgres-dw  → wadw  (opcional servicio dedicado; o mismo server + DB)
  redis / minio / ai-runtime  (sin cambio de rol)
```

### 6.2 Schemas lógicos dentro de wadw

| Schema | Rol |
|--------|-----|
| `ctl` | watermarks, pipeline_runs, pipeline_run_steps, known_errors |
| `stg` | tablas staging por pipeline (`stg_orders_lines`, …) — truncate/replace por run o append+partition date |
| `dw` | dimensiones, hechos, rollups diarios |

### 6.3 Convenciones

- Nombres: `dim_*`, `fact_*`, `agg_*_daily`.
- PK surrogate `bigserial` o UUID; **siempre** `company_id UUID NOT NULL`.
- Soft keys de negocio: `source_id` (UUID OLTP) + `company_id` únicos donde
  aplique.
- Timestamps `TIMESTAMPTZ` UTC; timezone de presentación = tenant (en query).
- Moneda/qty: `NUMERIC(20,6)` alineado a OLTP.
- `row_hash` opcional para detectar cambios en SCD.
- `loaded_at`, `pipeline_run_id` en facts para auditoría de carga.
- Índices: `(company_id, <fecha>)`, `(company_id, <dim_fk>)`.
- Particionado por rango de fecha en facts de alto volumen **cuando** una
  tabla supere umbral (~10–20M filas) — no anticipar en MVP vacío.

### 6.4 Dimensiones (v1)

| Dimensión | Origen principal | Notas |
|-----------|------------------|-------|
| `dim_company` | `platform.company` | Conforme tenants activos |
| `dim_date` | calendario estático | Generada por comando (no seed en migration de negocio) |
| `dim_facility` / warehouse | `facilities` | Por company |
| `dim_location` | locations | Degenerada o late-arriving |
| `dim_reference` (SKU) | `inventory.reference` | SCD2 ligero si cambian attrs analíticos |
| `dim_party` (customer/supplier) | `third_parties` | kind |
| `dim_operator` | users tenant / assigned_to | PII mínima (id + display opcional) |
| `dim_order_status` / priority / source | enums | Conformadas |

### 6.5 Hechos (v1 alineados a HUs)

| Hecho | Pipeline | Grano |
|-------|----------|-------|
| `fact_stock_position_snapshot` | inventory | posición × día (o cambio) |
| `fact_stock_movement` | inventory | 1 movimiento |
| `fact_stock_adjustment` / `fact_cycle_count` | inventory / operations | 1 evento |
| `fact_receipt` / `fact_receipt_line` | receiving | cabecera / línea |
| `fact_putaway_task` | receiving | 1 tarea |
| `fact_order` / `fact_order_line` | orders | cabecera / línea + hitos |
| `fact_pick_task` | picking | 1 pick |
| `fact_transfer` | operations | 1 transfer |

**Rollups:** `agg_order_kpi_daily`, `agg_inventory_kpi_daily`,
`agg_picking_kpi_daily` — alimentan strips/dashboards sin escanear facts
crudos (coherente con `order_kpi_daily` de HUs).

### 6.6 Versionado de esquema DW

- Migraciones Django del app analytics **solo** contra alias `analytics`.
- Versionar contratos de fila (Pydantic) en `core/analytics/domain/schemas.py`.
- Cambios breaking de fact → nuevo pipeline version (`orders_v2`) o columna
  nullable + backfill job; no silenciar en caliente.

### 6.7 Estrategia de crecimiento

| Horizonte | Acción |
|-----------|--------|
| 0–12 meses | Postgres wadw, facts + daily aggs, sin partición |
| 12–24 meses | Partición mensual facts calientes; retención cruda N meses |
| 24+ meses | Evaluar ClickHouse/EL T: cambiar adaptador `IAnalyticsStore`, mantener pipelines |

---

## 7. Motor ETL (y preparación ELT)

### 7.1 Flujo MVP (ETL)

```
Extract (OLTP, schema_context)
  → rows tipadas (Pydantic)
  → Transform (Python puro / SQL ligero)
  → Load (upsert dims, append/upsert facts en dw.*)
```

Staging (`stg`) se usa desde el día 1 aunque el transform sea en Python:
permite reprocesar sin re-extraer y prepara ELT.

### 7.2 Flujo futuro (ELT)

```
Extract → Load raw/stg (mínima tipificación)
  → Transform in-warehouse (SQL / motor analítico)
  → Marts dw.*
```

Para no reescribir el sistema:

- `IPipeline` orquesta pasos abstractos `extract → load_staging → transform → publish_mart`.
- En ETL actual, `transform` corre in-process y `publish_mart` escribe dims/facts.
- En ELT, `transform` delega a `IAnalyticsStore.execute_transform(plan)`.

### 7.3 Contratos (borrador)

```python
class IAnalyticsStore(ABC):
    def upsert_dimension(self, name: str, rows: list[dict]) -> int: ...
    def append_facts(self, name: str, rows: list[dict]) -> int: ...
    def merge_facts(self, name: str, rows: list[dict], keys: list[str]) -> int: ...
    def query(self, request: AnalyticsQuery) -> AnalyticsResult: ...
    def execute_transform(self, plan: TransformPlan) -> TransformResult: ...  # ELT

class IPipeline(ABC):
    key: str  # 'inventory' | 'orders' | ...
    def run(self, ctx: PipelineContext) -> PipelineResult: ...
```

Implementación inicial: `PostgresAnalyticsStore` (psycopg / Django connections
`using('analytics')`). Futuro: `ClickHouseAnalyticsStore`.

### 7.4 Por qué no Airflow / no segundo Celery

Ya hay Beat + workers + locks + monitor + incidentes. Un orquestador paralelo
duplicaría observabilidad y ops. **Un solo bus de tareas.**

---

## 8. Multi-tenant en analítica

### 8.1 Decisión: shared schema + `company_id`

| Enfoque | Veredicto |
|---------|-----------|
| Schema-per-tenant en wadw | ❌ Costoso, rompe agregaciones admin, migra mal a ClickHouse |
| DB-per-tenant | ❌ Inoperable a escala SaaS |
| **Tablas compartidas + `company_id`** | ✅ Estándar DW; barato; RLS opcional después |

### 8.2 Estrategias de procesamiento

| Modo | Mecánica |
|------|----------|
| Un tenant | `pipeline.run` + `TenantTask(schema_name=…)` |
| Todos | Task orquestadora lista companies activas → `apply_async` por schema (fan-out) |
| Subconjunto | Idem con filtro (`plan_tier`, `company_ids`, flag) |
| Paralelo | Fan-out Celery; `redis_lock(f'analytics:{pipeline}:{schema}')` evita solapes |
| Aislamiento | Extract solo ve su schema OLTP; load sella `company_id`; queries tenant exigen `company_id` del JWT |

### 8.3 Contaminación cruzada — controles

1. `PipelineContext.company_id` obligatorio en load.
2. APIs client: `company_id` del tenant autenticado, nunca del body libre.
3. Tests de regresión: query sin filtro de company debe fallar en capa de
   aplicación.
4. (Opcional Fase 6+) Postgres RLS por `app.company_id`.

---

## 9. Pipelines independientes

| Pipeline key | Fuentes OLTP | Hechos destino | Prioridad |
|--------------|--------------|----------------|-----------|
| `dimensions` | company, facilities, references, parties | dims | P0 (prerrequisito) |
| `inventory` | stock positions/movements, balances | stock facts | P0 |
| `orders` | orders + lines + hitos | order facts | P0 |
| `receiving` | receipts, lines, putaway | receipt facts | P1 |
| `picking` | pick tasks | pick facts | P1 |
| `operations` | transfers, cycle counts | ops facts | P1 |
| `packing` | (cuando exista módulo) | pack facts | P2 |
| `dispatch` | (cuando exista) | dispatch facts | P2 |
| `returns` | (cuando exista) | return facts | P2 |
| `rollup_daily` | facts dw | `agg_*_daily` | P0 tras facts |

Cada pipeline: propio watermark, propio schedule, propio lock, propios tests.

---

## 10. Procesamiento incremental

### 10.1 Watermarks (`ctl.pipeline_watermarks`)

```
(company_id, pipeline_key) → {
  cursor_ts,      -- occurred_at / updated_at
  cursor_id,      -- UUID desempate
  cursor_version, -- p.ej. InventoryPosition.version
  strategy,       -- 'ts' | 'id' | 'version' | 'snapshot_date'
  updated_at
}
```

### 10.2 Estrategias por dominio

| Dominio | Estrategia |
|---------|------------|
| Movements / picks / receipts cerrados | `occurred_at` / `completed_at` + id |
| Positions (estado actual) | snapshot diario **o** `updated_at` + version |
| Orders | `updated_at` + merge por `source_id` (hitos pueden llegar tarde) |
| Dims SCD | hash de attrs analíticos; upsert |

### 10.3 Reproceso

- Comando / task: `analytics.reprocess(pipeline, company_id?, from_ts, to_ts)`.
- Borra o marca partición lógica de facts en rango + reset watermark + rerun.
- Full refresh solo con lock y ventana de mantenimiento.

---

## 11. Scheduler (Celery + RedBeat)

Extender `build_beat_schedule()` (mismo archivo, convenciones existentes:
`expires`, UTC, nombres `<feature>.<verb>`):

| Entrada Beat | Task | Cadencia sugerida (inicial) |
|--------------|------|-----------------------------|
| `analytics.orchestrate-dimensions` | fan-out dims | 0 2 * * * |
| `analytics.orchestrate-inventory` | fan-out inventory | */30 * * * * |
| `analytics.orchestrate-orders` | fan-out orders | */15 * * * * |
| `analytics.orchestrate-receiving` | fan-out | 0 * * * * |
| `analytics.orchestrate-picking` | fan-out | */20 * * * * |
| `analytics.rollup-daily` | rollup (puede ser global SQL por company batch) | 30 5 * * * |

Patrón de fan-out (igual espíritu que health de connectors / inbox):

1. Task plataforma (sin schema) lista tenants.
2. Encola `TenantTask` por `schema_name` + `pipeline_key`.
3. Worker adquiere lock → lee watermark → extract → transform → load →
   actualiza watermark → registra run.

Prioridades Celery: cola `analytics` opcional (no mezclar con purgas cortas);
si se añade, documentar en Compose/worker `-Q celery,analytics`.

Reintentos: heredar `BaseTask` (transitorios); errores de datos → run `failed`
sin flood de retry.

---

## 12. Observabilidad

### 12.1 En wadw (`ctl`)

| Tabla | Contenido |
|-------|-----------|
| `pipeline_runs` | pipeline, company_id, status, trigger, started/finished, rows_in/out, error |
| `pipeline_run_steps` | extract / stage / transform / load / watermark |
| `pipeline_watermarks` | cursores |
| `pipeline_run_errors` | detalle fila/lote (opcional) |

### 12.2 En plataforma (reutilizar)

- Envolver orquestadores con `track_task_run` → `automated_task_runs` visibles
  en admin task_monitor.
- Añadir entradas al `TASK_CATALOG` para las tasks analytics.
- Logger `app.tasks` / `app.analytics`.
- Fallo final → incidente vía puerto existente (`incident_port`).

No duplicar una tercera UI de monitoreo en el MVP.

---

## 13. Dashboards, KPIs y reportes

Frontera ya definida en HUs:

- **Eje 5** (módulos operativos): definen indicadores y hechos.
- **Eje 6 / analytics**: exploran, comparan, exportan.
- Strip WEB operativo puede leer **aggs diarios** o APIs cortas; no facts crudos
  en el request de piso.

Superficies futuras (Fase 6):

| Superficie | Backend |
|------------|---------|
| Dashboard inventario / recepción / picking / packing / despachos | `client/features/analytics` |
| Productividad / comercial | aggs + dims party |
| Financiero | diferir hasta modelo de costo |
| Admin plataforma | agregados anónimos/count por tenant (sin PII) |

Features catalog (nombres ya citados en HUs; cableado diferido):
`dashboard.kpis`, `analytics.operational-kpis`, `analytics.picking-metrics`,
`analytics.dispatch-metrics`, `analytics.export-reports`, …

---

## 14. assistant e IA

El DW es la fuente de **cubo 3** (ML) y de tools de lectura histórica del
copiloto:

| Necesidad Assistant | Origen |
|---------------------|--------|
| “¿Cómo va el OTIF esta semana?” | `agg_order_kpi_daily` / query store |
| Tendencias / series | rollups |
| Predicciones | modelos Fase 5 entrenados sobre export DW |
| RAG documental | sigue en MinIO — **no** mezclar con facts |

Diseño:

- Tools del agente llaman use cases analytics (misma frontera de tenant).
- Nunca SQL libre del LLM sobre wadw en MVP.
- Export ML-ready = vistas o job que escribe dataset por `company_id` (plan-ia
  Fase 4).

---

## 15. Acoplamiento con otros planes

| Plan | Relación |
|------|----------|
| [plan-ia](../plan-ia/00-resumen-teorico.md) | Fase 4 instrumentación ↔ extractors; Fase 5 ML consume DW; Fase 3 tools leen aggs |
| [plan-integrations](../plan-integrations/00-resumen-teorico.md) | Patrón ports/runner; datos ERP llegan al OLTP primero, luego al DW vía pipeline `orders` |
| HUs operativas | Diccionario KPI/hechos; DW no redefine fórmulas sin actualizar HUs |

---

## 16. Mapa de fases

| Fase | Entrega | ¿Código de negocio KPI? |
|------|---------|-------------------------|
| **0** | `wadw` en compose/settings, router, healthcheck | No |
| **1** | `core/analytics` ports + fake store + tests unit | No |
| **2** | Schemas `ctl`/`stg`/`dw` mínimos + dims calendario/company | Estructura sí |
| **3** | Runner ETL, watermarks, tasks Beat orchestrate stub | Stub pipeline |
| **4** | Pipelines `dimensions`, `inventory`, `orders` + rollup orders | Sí (MVP) |
| **5** | `receiving`, `picking`, `operations` + rollups | Sí |
| **6** | APIs lectura tenant (+ admin básico) | Consumo |
| **7** | Tools Assistant + export ML-ready | IA |

Detalle y checklists: archivos `fase-*.md`.

---

## 17. Bitácora de decisiones

| Fecha | Decisión |
|-------|----------|
| 2026-08-02 | Se crea el plan tras auditoría del mono; **no** hay implementación aún. |
| 2026-08-02 | DW = PostgreSQL `wadw` separado del OLTP; alias Django `analytics`. |
| 2026-08-02 | Multi-tenant analítico = **shared tables + `company_id`**, no schema-per-tenant en wadw. |
| 2026-08-02 | Motor = Celery existente (`TenantTask`, Beat, locks, task_monitor); no Airflow. |
| 2026-08-02 | Módulo transversal `core/analytics/` gemelo de `core/integrations`. |
| 2026-08-02 | ETL primero con `stg` desde día 1 para migrar a ELT sin reescribir orquestación. |
| 2026-08-02 | MVP de pipelines: dimensions + inventory + orders; packing/dispatch/returns cuando existan en OLTP. |
| 2026-08-02 | KPIs/fórmulas se toman de `docs/hu-operative/**/07-indicadores-analiticas`. |
| 2026-08-02 | Entitlements `analytics.*`: diseñar nombres, **diferir cableado** según regla del repo. |
| 2026-09-25 | **Fase 0 cerrada:** `DATABASES['analytics']` → `wadw`, `AnalyticsRouter` antes de `TenantSyncRouter`, init Docker + healthcheck dual, tests unitarios. |
| 2026-09-25 | **Fase 1 cerrada:** `core/analytics` ports + `FakeAnalyticsStore` + `PipelineRunner` + `NullPipeline`; `ANALYTICS_STORE=fake` default. |
| 2026-09-25 | **Fase 2 cerrada:** schemas `ctl`/`stg`/`dw`, app `analytics_ctl`, `PostgresAnalyticsStore`, `migrate_analytics` / `load_dim_date` / `sync_dim_company`. |
