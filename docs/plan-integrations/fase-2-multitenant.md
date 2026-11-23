# FASE 2 — Capa multitenant y MVP Pedidos (SAP / SIESA)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 1](fase-1-capa-transversal.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-tests.md)

> **Continuidad — qué se hizo en la Fase 1.** La Fase 1 construyó `core/integrations/`:
> puertos, `ConnectorRunner`, registry, secret store cifrado, idempotencia,
> conflict resolver WMS_WINS, stubs SAP/SIESA y facade. **Con esa tubería lista**,
> la Fase 2 añade persistencia, catálogo platform, instancias por tenant y el
> primer flujo productivo: **sync batch de Pedidos**.

**Objetivo:** que cada tenant configure una o más conexiones (SAP, SIESA, apps),
ejecute sync batch de pedidos, y que el admin de plataforma gobierne el catálogo
de conectores — respetando `core/access` y features `integrations.*`.

**Dependencia de dominio:** requiere contrato mínimo en
`client/features/warehouse/orders/` (o nombre definitivo del módulo Pedidos):

- `CreateOrderFromIntegrationUseCase` (inbound)
- `ListOrdersPendingOutboundSyncUseCase` (outbound)
- `MarkOrderSyncedUseCase` (external_ref + last_sync_at)

Si orders aún no existe, crear **interfaces + fake repository** en integraciones
y sustituir cuando el módulo esté listo (mismo patrón que `FakeFlagStore`).

### Estructura objetivo

```
platform/features/integrations/connector_catalog/
├── models.py                   # ConnectorDefinition (public)
├── domain/
├── application/
├── infrastructure/
├── presentation/               # API admin CRUD catálogo
└── migrations/

client/features/integrations/
├── connection/
│   ├── models.py               # IntegrationConnection, TenantSecret
│   ├── domain/
│   ├── application/            # CRUD, test_connection, rotate_secret
│   ├── infrastructure/
│   └── presentation/           # API tenant IT
├── mapping/
│   ├── models.py               # FieldMapping (entity=order)
│   └── ...
├── sync/
│   ├── models.py               # SyncRun, SyncOutbox, SyncInbox
│   ├── application/
│   │   ├── run_order_sync.py
│   │   └── schedule_sync.py
│   ├── infrastructure/
│   ├── tasks/                  # Celery TenantTask
│   └── presentation/
└── facade/
    └── __init__.py             # entry points para otros módulos
```

### Modelo de datos

#### Platform — `ConnectorDefinition` (schema `public`)

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `key` | `sap`, `siesa`, `webhook-inbound`, … |
| `kind` | ERP \| PROVIDER \| APP |
| `name`, `description` | UI |
| `version` | semver del conector la base |
| `capabilities` | JSON: `["order.pull", "order.push"]` |
| `config_schema` | JSON Schema de campos de conexión (URL, client_id, …) |
| `is_active` | catálogo |

#### Tenant — `IntegrationConnection`

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `connector_key` | FK lógica a catálogo |
| `name` | alias del cliente ("SAP Producción Bogotá") |
| `environment` | PROSANDBOX \| CLIENT_TEST \| CLIENT_PROD |
| `config` | JSON no sensible (base_url, company_code, …) |
| `status` | ACTIVE \| PAUSED \| DEGRADED \| ERROR |
| `secret_id` | FK a TenantSecret |
| `schedule_cron` | batch (nullable) |
| `last_sync_at`, `last_error` | salud |
| `created_by` | user_id |

#### Tenant — `TenantSecret`

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `connection_id` | FK |
| `ciphertext` | bytes |
| `key_version` | rotación |
| `rotated_at` | auditoría |

#### Tenant — `FieldMapping` (MVP: entity=`order`)

| Campo | Notas |
|-------|--------|
| `connection_id` | FK |
| `entity` | `order` |
| `direction` | INBOUND \| OUTBOUND |
| `rules` | JSON: `[{source, target, transform?}]` |
| `is_active` | |

#### Tenant — `SyncRun`

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `connection_id` | FK |
| `entity` | `order` |
| `direction` | PULL \| PUSH \| BIDIRECTIONAL |
| `status` | PENDING \| RUNNING \| SUCCESS \| PARTIAL \| FAILED |
| `started_at`, `finished_at` | |
| `stats` | JSON: created, updated, skipped, errors |
| `dry_run` | bool |

#### Tenant — `SyncOutbox` / `SyncInbox` (estructura mínima)

Preparar tablas para visión híbrida futura; Fase 2 puede dejar inbox vacío.

### Flujo MVP — Sync batch de Pedidos

```
┌─────────────┐    cron/manual     ┌──────────────────┐
│ Celery Beat │ ─────────────────► │ RunOrderSyncTask │
└─────────────┘                    └────────┬─────────┘
                                            │ TenantTask(schema)
                                            ▼
                                   ┌────────────────────┐
                                   │ RunOrderSyncUseCase │
                                   └────────┬───────────┘
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
            core/access check      get_connector(SAP|SIESA)   mapping rules
            integrations.order-sync
                    │
        PULL ───────┴─────── PUSH
         │                    │
         ▼                    ▼
 CreateOrderFromIntegration   ListOrdersPendingOutbound
 + ConflictResolver WMS_WINS  + push_entities + MarkOrderSynced
```

### Conectores SAP y SIESA (primera implementación real)

| Conector | Protocolo inicial (batch) | Notas |
|----------|---------------------------|-------|
| **SAP** | REST/OData o API expuesta por cliente | Adapter traduce a `OrderIntegrationDTO` |
| **SIESA** | REST API SIESA | Mismo contrato interno |

Ambos implementan `IConnector`; diferencias solo en `infrastructure/` del
conector dentro de `core/integrations/connectors/erp/`.

Contratos HTTP exactos se validan contra `base-prosandbox` (Fase 6).

### Entitlements y permisos

Antes de cada operación:

```python
from core.access import check_feature  # o patrón existente
check_feature('integrations.order-sync', context)
```

Roles IT del cliente: permiso nuevo `integrations.manage_connections` (security/roles).

### API tenant (presentation)

| Endpoint | Acción |
|----------|--------|
| `GET /api/v1/integrations/connections/` | listar |
| `POST /api/v1/integrations/connections/` | crear |
| `POST .../test/` | test connection |
| `POST .../dry-run/` | dry-run sync orders |
| `POST .../sync/` | disparo manual batch |
| `GET /api/v1/integrations/sync-runs/` | historial |
| `CRUD /api/v1/integrations/mappings/` | mapeos pedidos |

Registrar rutas en `base/urls.py` (mundo client).

### API platform (presentation)

| Endpoint | Acción |
|----------|--------|
| `CRUD /platform/integrations/catalog/` | catálogo conectores |
| `GET /platform/integrations/health/` | vista agregada cross-tenant (soporte) |

Registrar en `base/urls_public.py`.

### Celery

```python
@shared_task(base=TenantTask, name='integrations.sync_orders')
def sync_orders_task(connection_id, dry_run=False):
  ...
```

- `redis_lock` por `{schema}:{connection_id}` para evitar sync concurrente.
- Schedule: `django-celery-beat` por conexión o entry global con fan-out.

### Facade para otros módulos

```python
# client/features/integrations/facade/__init__.py
def enqueue_order_outbound(order_id, connection_id=None): ...
def on_order_status_changed(order_id, new_status): ...  # outbox futuro
```

**Actividades:**

- [x] Crear `platform/features/integrations/connector_catalog/` (hexagonal completo).
- [x] Seed catálogo: SAP, SIESA (`manage.py` o migración data).
- [x] Crear `client/features/integrations/connection/` con modelos y CRUD.
- [x] Implementar `DjangoTenantSecretRepository` usando `EncryptedSecretStore`.
- [x] Crear `mapping/` con CRUD y validación de reglas mínimas.
- [x] Crear `sync/` con `SyncRun`, use cases y tasks Celery.
- [x] Implementar `RunOrderSyncUseCase` (pull + push batch).
- [x] Implementar `SapConnector` y `SiesaConnector` (HTTP real o prosandbox URL).
- [x] Cablear `CreateOrderFromIntegrationUseCase` (orders o stub).
- [x] Integrar `core/access` + feature `integrations.order-sync`.
- [x] Integrar `integration_logger` en cada operación.
- [x] Endpoints presentation tenant + platform.
- [x] Registrar apps en `INSTALLED_APPS` y URLs.
- [ ] Migraciones `migrate_schemas` (ejecutar en cada entorno).

**Definición de Done de la Fase 2:**

- [x] Tenant con plan que incluye `integrations.order-sync` puede crear conexión SAP o SIESA.
- [x] Test connection y dry-run funcionan.
- [x] Sync batch manual crea/actualiza pedidos (inbound) y marca outbound.
- [x] Re-ejecutar sync no duplica pedidos (idempotencia verificada).
- [x] WMS gana en conflicto simulado.
- [x] Soporte puede listar salud cross-tenant vía API platform.
