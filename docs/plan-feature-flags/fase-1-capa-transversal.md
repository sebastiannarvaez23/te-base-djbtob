# FASE 1 — Capa transversal (`core/flags/`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-capa-datos.md)

> **Continuidad — punto de partida.** Es la **primera fase de construcción**, así
> que no hay fase anterior que resumir. Su único prerequisito es el
> [resumen teórico](00-resumen-teorico.md): fronteras con `core/access` / roles /
> parámetros, targeting por `COMPANY` / `USER` / `COUNTRY` / `STATE` / `CITY`,
> fail-safe a lógica antigua, API booleana y ciclo de vida de flags. La Fase 1
> monta la **tubería de evaluación** que todas las fases siguientes consumen.
>
> **Qué queda explícitamente fuera de esta fase (se implementa después):**
> modelos Django, migraciones, API admin, caché Redis de persistencia, auditoría
> de mutaciones y pantalla en `base-admin-web`. Aquí solo existe evaluación en
> memoria vía `FakeFlagStore` (y el contrato `IFlagStore`).

**Objetivo:** construir el módulo transversal de evaluación de release flags
(puertos, estrategias de scope, evaluador, facade, keys tipadas) **sin**
persistencia ni HTTP. Al terminar, cualquier use case puede ramificar lógica
nueva vs antigua con una línea, y los tests del núcleo corren sin BD.

**Descripción detallada:** Es el equivalente para release flags de lo que
`core/ai/` es para IA y `core/access` es para entitlements — pero con
responsabilidad distinta: **solo** decide si la implementación nueva aplica al
contexto. Se definen contratos de dominio, matchers extensibles por tipo de
scope, un evaluador fail-safe y la facade pública `is_enabled`. El store real
(BD + caché) se enchufa en la Fase 2 sin cambiar call sites.

### Estructura objetivo

```
core/flags/
├── __init__.py              # facade pública
├── domain/
│   ├── interfaces.py        # IFlagStore, IScopeMatcher
│   ├── schemas.py           # FlagDefinition, FlagScope, FlagContext
│   └── enums.py             # FlagType, FlagStatus, ScopeType
├── application/
│   └── evaluator.py         # FlagEvaluator
├── infrastructure/
│   └── fake_store.py        # FakeFlagStore (tests / default hasta Fase 2)
├── scopes/
│   ├── base.py
│   ├── company.py
│   ├── user.py
│   ├── country.py
│   ├── state.py
│   ├── city.py
│   └── registry.py
├── keys.py                  # FlagKeys (constantes tipadas)
└── config.py                # get_flag_store()
```

**Actividades:**

- [x] Crear `core/flags/domain/enums.py`: `FlagType` (`RELEASE`, `OPS`),
      `FlagStatus` (`DRAFT`, `ACTIVE`, `CERTIFIED`, `DISABLED`, `ARCHIVED`),
      `ScopeType` (`COMPANY`, `USER`, `COUNTRY`, `STATE`, `CITY`).
- [x] Crear `core/flags/domain/schemas.py`: `FlagContext` (con
      `company_id`, `user_id`, `country`, `state`, `city` y
      `from_request(request)`), `FlagScope`, `FlagDefinition`.
- [x] Crear `core/flags/domain/interfaces.py`: puertos `IFlagStore` (obtener
      definición por key / listar activas) e `IScopeMatcher` (`matches(scope,
      context) -> bool`).
- [x] Implementar matchers en `core/flags/scopes/`:
      `CompanyScopeMatcher`, `UserScopeMatcher`, `CountryScopeMatcher`,
      `StateScopeMatcher`, `CityScopeMatcher`, más `ScopeMatcherRegistry`
      extensible.
- [x] Implementar `FlagEvaluator`: reglas de evaluación (solo `ACTIVE` +
      `enabled`; sin scopes = global; con scopes = OR; desconocida / no activa
      = `False`; excepción = `False` + log).
- [x] Implementar `FakeFlagStore` para tests y arranque sin BD.
- [x] Implementar `core/flags/config.py`: `get_flag_store()` (default `fake`
      hasta que la Fase 2 registre el adaptador Django/caché).
- [x] Implementar facade en `core/flags/__init__.py`:
      `is_enabled(key, context) -> bool`, exports de `FlagContext`, `FlagKeys`,
      enums necesarios.
- [x] Crear `core/flags/keys.py` con la clase/módulo `FlagKeys` (puede iniciar
      vacío o con constantes de ejemplo documentadas; sin strings mágicos en
      call sites futuros).
- [x] Documentar en el docstring del paquete el patrón de uso, el orden respecto
      a suscripción/rol, y la convención de limpieza al certificar.
- [x] Tests unitarios del núcleo (desde el día 1 de esta fase):
      - Matchers: match / no match / atributo ausente en contexto.
      - Evaluador: draft, disabled, certified, archived, active global, active
        con scopes COMPANY/USER/COUNTRY/STATE/CITY, OR entre scopes, key
        desconocida, store que lanza → `False`.
      - `FlagContext.from_request` (con/sin tenant, con/sin user).
      - Facade `is_enabled`.

**Definición de Done de la Fase 1:**

- [x] Existe `FakeFlagStore` intercambiable por el puerto `IFlagStore`.
- [x] Un use case de prueba (o test de integración ligera del evaluador) puede
      ramificar con `is_enabled(FlagKeys.…, ctx)` sin tocar platform ni BD.
- [x] Un fallo simulado del store **no** rompe la evaluación (devuelve `False`).
- [x] Añadir un nuevo `ScopeType` requiere solo un matcher + registro, no
      cambiar el evaluador.
- [x] Tests unitarios del núcleo en verde bajo `core/tests/unit/flags/`.
