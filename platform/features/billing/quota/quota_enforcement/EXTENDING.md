# Cupos por entidades activas — cómo extender

Documentación para implementar topes de suscripción sobre **cantidad de
recursos activos** (usuarios, bodegas, referencias, …) sin tocar billing ni
el reconciliador central.

Estado actual: **base genérica lista** + **usuarios** como referencia.
Los demás dominios se cablean cuando producto defina los topes en admin.

---

## Conceptos

| Idea | Descripción |
|------|-------------|
| **Tope en admin** | `SubscriptionLimit` en un plan: `feature_key` + `max_value` + `validation_type=lifetime` |
| **Cupo activo** | `count(entidades ACTIVAS) ≤ max` — no cuenta creaciones históricas en Redis |
| **Gate preventivo** | Antes de crear o **activar**, validar cupo (`AccessChecker.ensure_quota_or_raise`) |
| **Reconciliación** | Tras cambio de plan / nuevo período: inactivar sobrantes automáticamente |

**No aplica** a topes de acción (pedidos/día, llamadas API, chat por ventana).
Esos siguen con Redis (`track_usage` / `daily` / `window`).

---

## Arquitectura (qué tocar y qué no)

```
Admin: SubscriptionLimit (max por plan + feature_key)
         │
         ▼
AccessChecker.check_feature / ensure_quota_or_raise
         │  uso actual ← enforcement_registry.count_active (BD)
         ▼
Crear / activar en use case ──► bloquea si activos ≥ max

Cambio de plan materializado (PeriodIssued)
         │
         ▼
ReconcileCompanyQuotasUseCase (billing/quota_enforcement)
         │
         ▼
reconcile_company_quotas (core/access/reconcile.py)
         │  por cada tope lifetime con adaptador registrado
         ▼
adapter.deactivate(excedentes) — sin borrar
```

**No modificar** el listener ni `reconcile_company_quotas` al añadir dominios.

---

## Checklist por dominio nuevo

### 1. Catálogo y admin (cuando producto lo defina)

- Feature en `client/features/security/registration/feature_registry.py`
  (ej. `inventories.references-create` ya existe).
- Tope `lifetime` en base-admin-web para el plan (`SubscriptionLimit`).

La **misma `feature_key`** del tope debe usarse en adaptador y gates.

### 2. Adaptador (`IQuotaEntityAdapter`)

Ubicación recomendada: `{dominio}/quota_adapters.py` (tenant o public según tabla).

Implementar:

| Método | Contrato |
|--------|----------|
| `feature_key` | Igual que el tope en admin |
| `count_active` | `COUNT` de registros activos de la empresa |
| `list_active_entity_ids` | IDs activos **ordenados**: los **primeros** se conservan al reconciliar; los **últimos** se inactivan primero |
| `protected_entity_ids` | IDs que **nunca** se inactivan en reconciliación (vacío si no hay regla) |
| `deactivate` | Pasar a inactivo **sin delete** (misma semántica que la UI) |

**Schema tenant** (`client/features/warehouse/…`): envolver queries en
`schema_context` usando el `schema_name` de `Company`.

Referencia implementada: `client/features/security/registration/quota_adapters.py`
(`CompanyUsersQuotaAdapter`).

Registrar en `AppConfig.ready()` del módulo:

```python
def ready(self) -> None:
    from .quota_adapters import register_quota_adapters
    register_quota_adapters()
```

### 3. Gates en use cases (obligatorio)

En **crear** (si el recurso nace activo):

```python
AccessChecker.ensure_quota_or_raise(company, FEATURE_KEY)
```

En **activar** (toggle / patch `status=ACTIVE` / `is_active=True`):

- Solo si la transición es hacia activo.
- Misma `FEATURE_KEY` que el tope de creación.

En **desactivar**: no validar cupo.

Helper de usuarios (copiar patrón):

```python
# client/features/security/users/application/use_cases.py
def _ensure_users_quota(company_id):
    company = Company.objects.filter(id=company_id).first()
    if company:
        AccessChecker.ensure_quota_or_raise(company, USERS_QUOTA_FEATURE)
```

### 4. Presentation (API)

- `HasSubscriptionAccess` + `subscription_functionality` (feature de permiso).
- `subscription_check_quota = False` en la vista si el cupo se valida en el use case
  (evita doble chequeo); el use case llama `ensure_quota_or_raise`.
- `@track_usage(FEATURE_KEY)` en POST create **opcional** para cupos activos:
  el validador lee BD; `track_usage` es no-op si hay adaptador.

### 5. Tests

- Unit del adaptador (conteo, orden, protegidos, deactivate).
- Unit del use case (bloquea crear/activar con cupo lleno; desactivar libre).
- Opcional: test de reconciliación con adaptador mockeado (ver
  `platform/tests/unit/access/test_quota_enforcement.py`).

---

## Constantes de feature_key

Definir en el adaptador o en `core/access/enforcement.py` si es transversal:

```python
USERS_QUOTA_FEATURE = 'security.users.create'  # ya definido
```

Pendientes (ejemplos cuando producto confirme):

| Dominio | Feature key probable | Activo = |
|---------|----------------------|----------|
| Bodegas | `settings.warehouse-management` o nueva key | `status == 'ACTIVE'` |
| Referencias | `inventories.references-create` | `is_active` / estado catálogo |
| … | definir en catálogo | definir con dominio |

---

## Reconciliación automática

- **Cuándo:** evento `PeriodIssued` (upgrade, downgrade materializado, renovación).
- **Quién:** `PeriodIssuedQuotaListener` en `quota_enforcement/apps.py`.
- **Qué hace:** lee topes `lifetime` del plan nuevo; solo procesa features con
  adaptador en `enforcement_registry`.
- **Admin usuarios:** rol `Administrator` protegido (`ADMIN_ROLE_NAME`).

Si los protegidos superan el `max` del plan, se loguea `QUOTA_RECONCILE_INCOMPLETE`
y solo se inactivan los no protegidos posibles.

---

## Diferencia con `usage_registry` (payment-methods)

| | `usage_registry` | `enforcement_registry` |
|--|-------------------|------------------------|
| Uso | Re-sembrar Redis lifetime | Cupo de **activos** en BD |
| Cuándo | Eventos create/delete | Create + activate + reconciliación |
| Ejemplo | `settings.payment-methods.create` | `security.users.create` |

Una feature puede tener solo enforcement, solo usage counter, o ambos (evitar).

---

## Archivos de la base (no duplicar lógica fuera)

| Archivo | Rol |
|---------|-----|
| `core/access/enforcement.py` | Registry + `IQuotaEntityAdapter` |
| `core/access/reconcile.py` | Algoritmo genérico de reconciliación |
| `core/access/validators/lifetime.py` | Si hay adaptador → cuenta en BD |
| `core/access/checker.py` | `ensure_quota_or_raise`; track no-op con adaptador |
| `platform/features/billing/quota_enforcement/` | Listener `PeriodIssued` |
| `client/.../registration/quota_adapters.py` | **Referencia** usuarios |

---

## Orden recomendado al cablear dominios

1. Definir tope en admin + feature en catálogo.
2. Adaptador + registro en `ready()`.
3. Gates en use cases (crear + activar).
4. Permisos en API.
5. Tests.
6. Probar downgrade manual: empresa con excedentes → materializar plan → verificar inactivaciones.
