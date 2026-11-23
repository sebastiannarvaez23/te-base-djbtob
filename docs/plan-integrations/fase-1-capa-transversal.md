# FASE 1 — Capa transversal (`core/integrations/`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-multitenant.md)

> **Continuidad — punto de partida.** Es la **primera fase de construcción**. Su
> prerequisito es el [resumen teórico](00-resumen-teorico.md). No requiere el
> módulo `orders` terminado: define la tubería que Fase 2 y el dominio Pedidos
> consumirán. Patrones de referencia: `core/ai/`, `core/storage/`,
> `platform/features/billing/payments/domain/interfaces.py`.

**Objetivo:** construir el módulo transversal de integraciones (puertos,
runner, registry, resiliencia, secret store abstracto, observabilidad) **sin**
persistencia tenant ni conectores SAP/SIESA reales. Al terminar, cualquier
feature podrá invocar un conector con idempotencia y logging mediante una
facade, y los tests corren con `FakeConnector`.

**Qué queda explícitamente fuera de esta fase:**

- Modelos Django, migraciones, API HTTP.
- Conectores SAP/SIESA productivos (solo stubs/fake).
- UI admin o cliente.
- Jobs Celery de sync batch (se cablean en Fase 2).

### Estructura objetivo

```
core/integrations/
├── __init__.py                 # facade pública
├── config.py                   # get_connector_class(), get_secret_store()
├── domain/
│   ├── interfaces.py           # IConnector, IConnectorRegistry, ISecretStore, IIdempotencyStore
│   ├── schemas.py              # ConnectionProfile, SyncRequest, SyncResult, ExternalEntityRef
│   └── enums.py                # ConnectorKind, ConnectorProvider, SyncDirection, Environment, SyncStatus
├── application/
│   ├── connector_runner.py     # ejecuta operación con timeout, log, idempotencia
│   ├── sync_orchestrator.py    # orquesta pull/push batch (sin BD)
│   └── conflict_resolver.py    # política WMS_WINS
├── infrastructure/
│   ├── registry.py             # registro de clases por provider+version
│   ├── fake_connector.py       # FakeConnector para tests
│   ├── fake_secret_store.py
│   ├── idempotency.py          # RedisIdempotencyStore
│   └── resilience.py           # retry wrapper, circuit breaker lite
├── connectors/
│   ├── base.py                 # BaseConnector (template method)
│   ├── erp/
│   │   ├── sap/
│   │   │   └── connector.py    # stub (raise NotImplemented o fake)
│   │   └── siesa/
│   │       └── connector.py    # stub
│   └── app/
│       └── webhook_inbound.py  # contrato base inbound (stub)
└── observability/
    ├── integration_logger.py   # facade → client.logging.integration
    └── metrics.py              # contadores básicos (opcional en Fase 1)
```

### Puertos principales (`domain/interfaces.py`)

**`IConnector`** — contrato que todo adaptador cumple:

```python
class IConnector(ABC):
    provider: ConnectorProvider
    kind: ConnectorKind          # ERP | PROVIDER | APP

    def test_connection(self, profile: ConnectionProfile) -> ConnectionTestResult: ...
    def pull_entities(self, request: SyncRequest) -> SyncResult: ...
    def push_entities(self, request: SyncRequest) -> SyncResult: ...
    def dry_run(self, request: SyncRequest) -> DryRunResult: ...
```

**`ISecretStore`** — get/set/delete ciphertext; nunca expone en logs.

**`IIdempotencyStore`** — get/put con scope `{tenant}:{connection}:{op}`.

**`IConnectorRegistry`** — `resolve(provider, version) -> Type[IConnector]`.

### Facade pública (`core/integrations/__init__.py`)

```python
from core.integrations import run_connector_op, get_connector

# Uso en use case de orders (futuro):
connector = get_connector(profile)
result = run_connector_op(connector.pull_entities, request, context=ctx)
```

`run_connector_op` encapsula: idempotencia, timeout, integration log,
circuit breaker, degradación best-effort.

### Secret store (implementación Fase 1)

- `EncryptedSecretStore` con AES-GCM vía `cryptography`.
- Clave maestra: `INTEGRATIONS_SECRET_KEY` en settings (django-environ).
- `FakeSecretStore` para tests (dict en memoria).
- Sin modelo Django aún: Fase 2 persiste ciphertext en tenant.

### Resiliencia mínima

- Timeout por operación (`INTEGRATIONS_DEFAULT_TIMEOUT_SECONDS`).
- Reintentos solo en errores transitorios (HTTP 5xx, timeout, connection).
- Circuit breaker: tras N fallos (`INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD`),
  marcar conexión "degraded" en memoria (Fase 2 persiste estado).

### Errores

Añadir familia `INT_00x` en `core/errors/codes.py`:

| Código | Caso |
|--------|------|
| `INT_001` | Conector no encontrado |
| `INT_002` | Conexión fallida (test connection) |
| `INT_003` | Timeout |
| `INT_004` | Proveedor externo no disponible |
| `INT_005` | Conflicto de sync (WMS_WINS aplicado) |
| `INT_006` | Idempotencia / duplicado detectado |
| `INT_007` | Credenciales inválidas o expiradas |
| `INT_008` | Mapeo inválido |

Ejecutar `python manage.py syncerrors` tras añadir códigos.

### Conflict resolver

`ConflictResolver.resolve(inbound, current_wms) -> Resolution`:

- Si divergen campos críticos → mantener WMS, registrar `INT_005` en log,
  incluir diff en `SyncResult.warnings`.

### Integración con logging existente

`observability/integration_logger.py` traduce a
`IntegrationLogInputSchema` y delega en `LogManagerFactory` (no duplicar
persistencia).

**Actividades:**

- [x] Crear `core/integrations/domain/enums.py`.
- [x] Crear `core/integrations/domain/schemas.py`.
- [x] Crear `core/integrations/domain/interfaces.py`.
- [x] Implementar `BaseConnector` y `FakeConnector`.
- [x] Implementar stubs `SapConnector`, `SiesaConnector` (respuestas fake).
- [x] Implementar `ConnectorRegistry` + `config.py`.
- [x] Implementar `ConnectorRunner` con idempotencia y timeout.
- [x] Implementar `SyncOrchestrator` (orquestación in-memory).
- [x] Implementar `ConflictResolver` (WMS_WINS).
- [x] Implementar `EncryptedSecretStore` + `FakeSecretStore`.
- [x] Implementar `RedisIdempotencyStore` (+ fake para tests sin Redis).
- [x] Implementar `resilience.py` (retry + circuit breaker lite).
- [x] Implementar `integration_logger` facade.
- [x] Añadir `INT_00x` en `core/errors/codes.py` + `ES_OVERRIDES`.
- [x] Añadir settings en `base/settings/base.py`:
      `INTEGRATIONS_SECRET_KEY`, `INTEGRATIONS_DEFAULT_TIMEOUT_SECONDS`,
      `INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD`, `INTEGRATIONS_ENABLED` (default True).
- [x] Documentar en `CLAUDE.md` el módulo `core/integrations/`.
- [x] Tests smoke en `core/tests/unit/integrations/` (ver Fase 3).

**Definición de Done de la Fase 1:**

- [x] `FakeConnector` intercambiable por config/registry sin tocar dominio.
- [x] `run_connector_op` registra integration log y respeta idempotencia.
- [x] Caída simulada del externo no rompe el request (degrada / error controlado).
- [x] Secretos nunca aparecen en logs (`test_logging_redaction` compatible).
- [x] Stubs SAP/SIESA registrados y resolubles por registry.
