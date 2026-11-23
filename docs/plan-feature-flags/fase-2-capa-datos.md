# FASE 2 — Capa de datos y API admin (platform)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 1](fase-1-capa-transversal.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-tests.md)

> **Continuidad — qué se hizo en la Fase 1.** La Fase 1 construyó el módulo
> transversal `core/flags/`: enums (`FlagType`, `FlagStatus`, `ScopeType`),
> schemas (`FlagContext` con `company_id` / `user_id` / `country` / `state` /
> `city`, `FlagDefinition`, `FlagScope`), puertos `IFlagStore` e
> `IScopeMatcher`, matchers para `COMPANY` / `USER` / `COUNTRY` / `STATE` /
> `CITY`, `FlagEvaluator` fail-safe, `FakeFlagStore`, facade `is_enabled`,
> `FlagKeys` y tests unitarios del núcleo. Resultado: cualquier use case puede
> evaluar una release flag sin conocer persistencia. **Con esa tubería lista**,
> la Fase 2 añade la **fuente de verdad en schema público**, el CRUD admin, la
> caché en caliente y el adaptador real de `IFlagStore`.
>
> **Qué queda de la Fase 1 como punto de partida de esta fase:**
> - El evaluador y los matchers **no se reescriben**; solo se enchufa un store
>   real vía `get_flag_store()`.
> - `FakeFlagStore` se mantiene para tests y para el default seguro si el
>   adaptador Django no está disponible.
> - Las keys tipadas (`FlagKeys`) siguen viviendo en `core/flags/keys.py`.
>
> **Qué queda explícitamente fuera de esta fase (se implementa después):**
> consolidación completa de la matriz de tests (Fase 3) y la pantalla en
> `base-admin-web` (Fase 4). Esta fase sí incluye tests unitarios de use cases /
> repositorio / adaptador de store.

**Objetivo:** persistir feature flags en tablas independientes del schema
`public`, exponer CRUD admin con auditoría, cachear lecturas con el mismo
patrón que parámetros, y conectar el runtime de `core/flags` al snapshot
cacheado — todo con **cambio en caliente**.

**Descripción detallada:** Se crea la feature hexagonal
`platform/features/release/feature_flag/`, aislada de
`configuration/parameter`. Los modelos viven en `public`. Las mutaciones
invalidan `feature_flags:*` en Redis. El adaptador `CachedDjangoFlagStore`
implementa `IFlagStore` leyendo el snapshot cacheado (flags activas + scopes)
y el evaluador de la Fase 1 opera en memoria sobre ese snapshot.

### Estructura objetivo

```
platform/features/release/feature_flag/
├── models.py
├── apps.py
├── domain/
│   ├── interfaces.py
│   ├── schemas.py
│   └── enums.py            # espejo / reexport de tipos de dominio si aplica
├── application/
│   └── use_cases.py        # CRUD + scopes + invalidate_cache
├── infrastructure/
│   ├── repositories.py     # DjangoFeatureFlagRepository
│   └── flag_store.py       # adaptador IFlagStore (snapshot cacheado)
├── presentation/
│   ├── api.py
│   ├── serializers.py
│   └── urls.py
└── migrations/
```

### Modelo de datos (idea)

**`FeatureFlag`**

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `key` | único, machine-readable |
| `name`, `description` | UI admin |
| `flag_type` | `RELEASE` \| `OPS` (extensible) |
| `status` | ciclo de vida |
| `enabled` | interruptor maestro dentro de `ACTIVE` |
| `created_at`, `updated_at` | auditoría temporal |
| `owner` (opcional) | responsable de limpieza |

**`FeatureFlagScope`**

| Campo | Notas |
|-------|--------|
| `id` | UUID PK |
| `flag` | FK a `FeatureFlag` |
| `scope_type` | `COMPANY` \| `USER` \| `COUNTRY` \| `STATE` \| `CITY` |
| `scope_value` | string (UUID o valor de ubicación) |
| `is_active` | permite desactivar un scope sin borrarlo |

**Actividades:**

- [x] Crear app `platform.features.release.feature_flag` y registrarla en
      `SHARED_APPS` / settings.
- [x] Implementar modelos `FeatureFlag` y `FeatureFlagScope` + migración en
      schema público (`db_table` propios, p. ej. `release_feature_flags`,
      `release_feature_flag_scopes`).
- [x] Definir schemas Pydantic e interfaces de repositorio en `domain/`.
- [x] Implementar `DjangoFeatureFlagRepository`.
- [x] Implementar use cases: listar, obtener, crear, actualizar, eliminar,
      toggle `enabled` / cambio de `status`, gestionar scopes.
- [x] En cada mutación: `invalidate_cache('feature_flags:*')` (mismo patrón
      que `platform/features/configuration/parameter/application/use_cases.py`).
- [x] Cachear lecturas de listado/snapshot con `@use_case_cache(prefix='feature_flags')`.
- [x] Implementar adaptador `CachedDjangoFlagStore` (`IFlagStore`) que carga el
      snapshot de flags `ACTIVE` + scopes activos.
- [x] Cablear `get_flag_store()` en `core/flags/config.py` al adaptador real
      (setting opcional `FLAG_STORE=fake|django` para tests).
- [x] Presentation: serializers, views, `wrap_response`,
      `AdminTokenAuthentication`, urls.
- [x] Rutas: `platform/feature-flags/` en `base/urls.py` y `base/urls_public.py`.
- [x] Integrar `audit_log` en create / update / toggle / delete / cambios de
      scopes.
- [x] Añadir códigos de error `FLAG_*` en `core/errors/codes.py` si aplica
      (not found, duplicate key, invalid status transition, invalid scope).
- [x] Tests unitarios de esta capa:
      - Use cases CRUD y scopes (repo mockeado).
      - Invalidación de caché invocada en mutaciones.
      - Adaptador de store: snapshot → definiciones que el evaluador entiende.
      - Transiciones de estado que no deben evaluar como ON.

**Definición de Done de la Fase 2:**

- [x] Un admin autenticado puede crear/activar/desactivar una flag vía API
      platform.
- [x] Tras una mutación, la siguiente evaluación en runtime refleja el cambio
      **sin redeploy** (caché invalidada).
- [x] `is_enabled` en un use case usa el store real cuando `FLAG_STORE=django`
      (o default de producción).
- [x] Fallo de BD/caché en lectura del store sigue devolviendo `False` (lógica
      antigua).
- [x] Auditoría registrada en mutaciones.
- [x] Tests unitarios de use cases / store en verde bajo
      `platform/tests/unit/release/` (o ruta equivalente).
