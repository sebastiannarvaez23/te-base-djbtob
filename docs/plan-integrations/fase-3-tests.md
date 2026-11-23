# FASE 3 — Suite de tests unitarios

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 2](fase-2-multitenant.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-admin-web.md)

> **Continuidad — qué se hizo en la Fase 2.** Persistencia multitenant, catálogo
> platform, conexiones, mapeos, sync batch de pedidos SAP/SIESA, APIs y tasks
> Celery. La Fase 3 consolida la **matriz de pruebas** para que el núcleo y el
> MVP sean seguros de evolucionar.

**Objetivo:** cobertura unitaria exhaustiva de `core/integrations/` y de los use
cases críticos de `client/features/integrations/`, sin depender de SAP/SIESA
reales ni de Redis/Postgres cuando sea posible (fakes + mocks).

### Ubicación de tests

```
core/tests/unit/integrations/
├── conftest.py
├── test_registry.py
├── test_connector_runner.py
├── test_idempotency.py
├── test_conflict_resolver.py
├── test_secret_store.py
├── test_resilience.py
├── test_fake_connector.py
├── test_sap_connector.py          # sin HTTP real
├── test_siesa_connector.py
├── test_integration_logger.py
├── test_sync_orchestrator.py
└── test_config.py

client/tests/unit/integrations/
├── conftest.py
├── test_connection_use_cases.py
├── test_mapping_validation.py
├── test_run_order_sync.py
├── test_entitlement_gate.py
└── test_dry_run.py

platform/tests/unit/integrations/
└── test_connector_catalog.py
```

Marcar con `@pytest.mark.unit` según convención del proyecto.

### Matriz de escenarios — `core/integrations/`

| # | Componente | Escenario | Esperado |
|---|------------|-----------|----------|
| 1 | Registry | resolve SAP / SIESA / unknown | clase correcta / INT_001 |
| 2 | ConnectorRunner | op exitosa | log + resultado |
| 3 | ConnectorRunner | timeout | INT_003, no side effects |
| 4 | ConnectorRunner | idempotencia hit | INT_006, sin re-ejecución |
| 5 | ConnectorRunner | error transitorio | retry N veces |
| 6 | ConnectorRunner | error negocio | sin retry |
| 7 | ConflictResolver | inbound vs WMS difieren | WMS_WINS + warning |
| 8 | ConflictResolver | inbound nuevo | acepta |
| 9 | EncryptedSecretStore | round-trip encrypt/decrypt | igual |
| 10 | EncryptedSecretStore | clave incorrecta | fallo controlado |
| 11 | Circuit breaker | N fallos | degraded |
| 12 | FakeConnector | pull/push/dry_run | contrato cumplido |
| 13 | Integration logger | payload con password | enmascarado |

### Matriz — sync Pedidos (Fase 2)

| # | Use case | Escenario | Esperado |
|---|----------|-----------|----------|
| 14 | RunOrderSync | pull 3 pedidos nuevos | 3 created |
| 15 | RunOrderSync | pull duplicado mismo external_id | 0 created, idempotente |
| 16 | RunOrderSync | push 2 pedidos pending | 2 synced |
| 17 | RunOrderSync | externo 500 | FAILED, sync_run registrado |
| 18 | RunOrderSync | dry_run=true | stats sin persistir orders |
| 19 | TestConnection | credenciales inválidas | INT_007 |
| 20 | Entitlement | sin integrations.order-sync | PERM / access error |
| 21 | Mapping | regla inválida | VAL_001 |
| 22 | Multi-connection | tenant con SAP + SIESA | sync independientes |

### Matriz — platform catalog

| # | Escenario | Esperado |
|---|-----------|----------|
| 23 | CRUD connector definition | OK |
| 24 | Desactivar conector | tenants no pueden crear nuevas conexiones de ese key |
| 25 | Health aggregate | cuenta degraded por tenant |

### Tests de API (opcional en esta fase)

Si el proyecto separa `@pytest.mark.api`, añadir en `client/tests/api/integrations/`:

- Crear conexión autenticado como IT admin.
- IT sin permiso → 403.
- Test connection endpoint.

### Chaos / resiliencia (mínimo)

Reutilizar espíritu de `platform/tests/unit/support/test_chaos_redis_down.py`:

- [x] Idempotency con Redis caído → degrada a BD-only o skip idempotency con log (documentar comportamiento).

**Actividades:**

- [x] Crear estructura `core/tests/unit/integrations/`.
- [x] Implementar matriz escenarios 1–13.
- [x] Crear `client/tests/unit/integrations/`.
- [x] Implementar matriz escenarios 14–22.
- [x] Crear `platform/tests/unit/integrations/`.
- [x] Implementar matriz escenarios 23–25.
- [x] Test chaos Redis (idempotencia).
- [x] Verificar `pytest -m unit` verde en CI.

**Definición de Done de la Fase 3:**

- [x] ≥ 25 escenarios unitarios documentados arriba implementados.
- [x] Ningún test llama a SAP/SIESA reales (HTTP mockeado o FakeConnector).
- [x] Cobertura de rutas críticas: runner, conflict, sync, entitlements.
- [x] `pytest -m unit` pasa en base.
