# Plan de Trabajo Feature Flags — Resumen teórico (base)

> **Propósito de este documento.** Es la hoja de ruta única y compartida para
> incorporar **feature flags de liberación** (release toggles) en la plataforma
> WMS de forma limpia, escalable y mantenible, alineada a **trunk-based
> development**. Está escrito para que **cualquier colega del equipo** entienda
> qué se va a construir, por qué, en qué orden, cómo se separa de suscripción /
> parámetros / roles, y cómo encaja en la arquitectura existente.
>
> **Cómo se usa.** Este archivo contiene la parte **teórica** (contexto,
> glosario, fronteras, arquitectura, targeting, ciclo de vida y mapa de fases).
> Cada fase de construcción vive en su propio archivo dentro de este mismo
> directorio `docs/plan-feature-flags/`. Cada fase tiene un bloque de
> **continuidad** (qué se hizo en la fase anterior y qué queda para empezar la
> actual), un objetivo, una descripción detallada y una lista de actividades con
> `[ ]` casillas de verificación. Marca `[x]` cuando una actividad esté
> **terminada y verificada** (ver *Definición de Done* de cada fase). No marques
> algo "a medias": si está en progreso, déjalo `[ ]` y anótalo en la bitácora al
> final de este documento.

---

## Índice

### Teoría (este archivo)

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Glosario: qué es (y qué no es) una feature flag aquí](#2-glosario-qué-es-y-qué-no-es-una-feature-flag-aquí)
3. [Fronteras con capas existentes](#3-fronteras-con-capas-existentes)
4. [Principios de arquitectura](#4-principios-de-arquitectura)
5. [Targeting: Company, User y ubicación (Country / State / City)](#5-targeting-company-user-y-ubicación-country--state--city)
6. [Ciclo de vida y limpieza de código](#6-ciclo-de-vida-y-limpieza-de-código)
7. [API de consumo y resiliencia](#7-api-de-consumo-y-resiliencia)
8. [Persistencia, caché y administración](#8-persistencia-caché-y-administración)
9. [Mapa de fases (resumen)](#9-mapa-de-fases-resumen)
10. [Bitácora de decisiones](#10-bitácora-de-decisiones)

### Fases de construcción (un archivo cada una)

- [FASE 1 — Capa transversal (`core/flags/`)](fase-1-capa-transversal.md)
- [FASE 2 — Capa de datos y API admin (platform)](fase-2-capa-datos.md)
- [FASE 3 — Suite de tests unitarios](fase-3-tests.md)
- [FASE 4 — Pantalla administrativa (`base-admin-web`)](fase-4-admin-web.md)

---

## 1. Contexto y objetivo

**base** es el backend de un WMS SaaS multi-tenant (django-tenants, un
schema PostgreSQL por empresa). El desarrollo operativo avanza hacia **trunk-based
development**: el código nuevo entra pronto a `main`, pero la **liberación** al
usuario se controla.

**Objetivo de este plan:** construir una base transversal de **feature flags de
liberación** que permita:

- Desplegar funcionalidad nueva detrás de un interruptor.
- Activar o apagar en **caliente** (sin redeploy) desde el administrador de
  plataforma (`base-admin-web` / APIs de `platform/`).
- Acotar la liberación por **empresa**, **usuario** o **ubicación geográfica**
  (`country`, `state`, `city` de la empresa).
- Ante fallo o flag apagada, ejecutar siempre la **lógica antigua** (reversión
  barata, bajo impacto).
- Facilitar la **limpieza** del código cuando la feature se certifica (retirar
  el camino viejo y la propia flag).

**No-objetivos (lo que este plan NO hace):**

- No reemplaza el control de acceso por **suscripción / plan** (`core/access`).
- No reemplaza **roles / permisos** del usuario.
- No reutiliza ni mezcla la tabla de **parámetros de sistema**
  (`platform/features/configuration/parameter`).
- No expone flags al cliente operativo (`base-client-web`): el backend es la única
  fuente de verdad.
- No implementa en la primera entrega políticas de caducidad automática ni
  enforcement en CI (solo convención documentada).

---

## 2. Glosario: qué es (y qué no es) una feature flag aquí

| Concepto | Qué es | Dónde vive hoy |
|----------|--------|----------------|
| **Release flag** (este plan) | Interruptor de liberación de código nuevo vs código antiguo | **Nuevo:** `core/flags` + tablas propias en `public` |
| **Entitlement de plan** | ¿El plan de la empresa incluye la capacidad y no superó el tope? | `core/access` + billing |
| **Rol / permiso** | ¿Este usuario puede operar el recurso? | Security / roles |
| **Parámetro de sistema** | Configuración global tipada de plataforma (`2FA_ENABLED`, etc.) | `core/parameters` + `configuration/parameter` |
| **Kill-switch de deploy** | Toggle en `.env` / settings (requiere redeploy) | `base/settings` (`AI_ENABLED`, `INCIDENT_*`, …) |

Una **release flag** responde solo a: *“¿ejecuto la implementación nueva o la
antigua para este contexto?”*. No responde a *“¿puede este tenant usar la
capacidad comercialmente?”* ni a *“¿tiene este usuario el rol?”*.

---

## 3. Fronteras con capas existentes

Orden de evaluación en un request de cliente:

```
Cliente → backend
  1. Suscripción / plan (core/access)     → si deniega, fin
  2. Rol / permiso del usuario            → si deniega, fin
  3. Use case de negocio
       └─ dentro de la lógica: feature flag (core/flags)
            ON  + scope match → lógica nueva
            OFF / sin match / fallo → lógica antigua
```

Regla explícita: **si el usuario no tiene acceso por suscripción (o por rol), la
feature flag de liberación nunca se evalúa para autorizar el recurso.** La flag
solo ramifica implementación **después** de que el request ya está autorizado.

| Capa | Relación con release flags |
|------|----------------------------|
| `core/access` | Independiente. Se ejecuta **antes**. |
| Roles | Independientes. Se ejecutan **antes**. |
| `core/parameters` | No se reutiliza el modelo. Sí el **patrón** de caché (`use_case_cache` / `invalidate_cache`). |
| Settings / `.env` | Fuera de alcance de este plan (ops de infraestructura). |

---

## 4. Principios de arquitectura

1. **Dos mundos, un contrato.**
   - `core/flags/`: evaluación pura (puertos, estrategias de scope, facade).
     Sin modelos Django, sin HTTP.
   - `platform/features/release/feature_flag/`: persistencia en schema `public`,
     use cases CRUD, API admin, auditoría.
2. **Puertos y adaptadores** (mismo espíritu que `core/ai/` y `core/storage/`).
   Los use cases de negocio dependen de `is_enabled(...)` / `IFlagStore`, nunca
   de modelos de platform.
3. **Open/Closed en targeting.** Cada dimensión de liberación es un
   `IScopeMatcher` registrable (`COMPANY`, `USER`, `COUNTRY`, `STATE`, `CITY`).
   Ampliar el espectro no requiere reescribir el evaluador.
4. **Fail-safe.** Cualquier error al evaluar → `False` → lógica antigua. El
   sistema prioriza resiliencia sobre la feature nueva.
5. **Defaults en código.** Flag desconocida o no `ACTIVE` → `False`.
6. **Keys tipadas.** Constantes en `core/flags/keys.py` (`FlagKeys`) para
   evitar strings mágicos y facilitar el grep al retirar flags certificadas.
7. **Solo booleana** en la primera entrega (`is_enabled` → `bool`). Sin
   variantes multivariate.
8. **Admin-only.** Gestión y monitoreo desde plataforma; el cliente operativo
   no conoce las flags.

---

## 5. Targeting: Company, User y ubicación (Country / State / City)

La liberación se parametriza por **scopes**. Un scope es un par
`(scope_type, scope_value)`.

| `scope_type` | `scope_value` (ejemplo) | Match contra |
|--------------|-------------------------|--------------|
| `COMPANY` | UUID de la empresa | `FlagContext.company_id` |
| `USER` | UUID del usuario | `FlagContext.user_id` |
| `COUNTRY` | valor de `Company.country` | `FlagContext.country` |
| `STATE` | valor de `Company.state` | `FlagContext.state` |
| `CITY` | valor de `Company.city` | `FlagContext.city` |

`Company` ya expone `country`, `state` y `city` en el schema público. El
contexto de evaluación se construye desde el request (tenant + usuario
autenticado):

```python
FlagContext(
    company_id=...,
    user_id=...,
    country=company.country,
    state=company.state,
    city=company.city,
)
```

**Reglas de match:**

- Flag `ACTIVE` + `enabled=True` **sin scopes** → rollout **global** (`True`).
- Con uno o más scopes → `True` si **al menos un** scope hace match (OR).
- Comparación de ubicación: igualdad de strings normalizada (trim; case según
  convención fijada en implementación, documentada en tests).
- Ampliar el espectro futuro (p. ej. un catálogo de regiones) = nuevo
  `ScopeType` + matcher, sin tocar el evaluador.

---

## 6. Ciclo de vida y limpieza de código

### Tipos de flag (extensibles)

| Tipo | Uso |
|------|-----|
| `RELEASE` | Liberación temporal de feature nueva (ciclo corto; se retira al certificar). |
| `OPS` | Kill-switch operativo (puede vivir más tiempo). |

Añadir tipos nuevos no debe romper el evaluador (enum / registro abierto).

### Estados

| Estado | ¿Se evalúa como ON posible? | Significado |
|--------|-----------------------------|-------------|
| `DRAFT` | No | Configurada, aún no participa. |
| `ACTIVE` | Sí (si `enabled=True` y scopes) | En producción. |
| `CERTIFIED` | No | Feature aceptada; señal para retirar código viejo y el `if is_enabled`. |
| `DISABLED` | No | Apagada de emergencia (hot off). |
| `ARCHIVED` | No | Histórico; ya no se evalúa. |

Solo `ACTIVE` + `enabled=True` puede devolver `True`.

### Limpieza (convención, Fase 1)

Cuando una flag pasa a `CERTIFIED`:

1. Dejar solo el camino nuevo en el use case.
2. Eliminar el `if is_enabled(...)` y la key de `FlagKeys`.
3. Archivar la flag en admin (`ARCHIVED`).

No hay política de caducidad automática en esta entrega.

---

## 7. API de consumo y resiliencia

API mínima (única forma recomendada de consumir flags en negocio):

```python
from core.flags import is_enabled, FlagContext, FlagKeys

ctx = FlagContext.from_request(request)

if is_enabled(FlagKeys.SOME_NEW_BEHAVIOR, ctx):
    return self._new_behavior(data)
return self._legacy_behavior(data)
```

- Vive **dentro** del use case (o se pasa `FlagContext` desde presentation).
- No hay permiso DRF ni middleware de flags: no autorizan recursos.
- Ante fallo de store, caché o matcher: log warning + `False`.
- Flag inexistente: `False`.

---

## 8. Persistencia, caché y administración

- Tablas **independientes** en schema `public` (no `configuration_parameters`).
- Feature: `platform/features/release/feature_flag/` (hexagonal completa).
- Lectura runtime: snapshot cacheado en Redis con el mismo patrón que
  parámetros (`@use_case_cache(prefix='feature_flags')` +
  `invalidate_cache('feature_flags:*')` en cada mutación).
- Cambio en caliente: el admin muta BD → se invalida caché → la siguiente
  evaluación lee el snapshot fresco.
- Auditoría: `audit_log` en create / update / toggle / delete / cambios de
  scopes (mismo patrón que parameters, company, etc.).
- Endpoints bajo `/platform/feature-flags/` con `AdminTokenAuthentication`,
  registrados en `base/urls.py` y `base/urls_public.py`.

---

## 9. Mapa de fases (resumen)

| Fase | Nombre | Entregable principal | Depende de |
|:----:|--------|----------------------|------------|
| **1** | Capa transversal (`core/flags/`) | Evaluador, scopes, facade, `FakeFlagStore`, tests del núcleo | — |
| **2** | Capa de datos y API admin | Modelos, repos, CRUD, caché, store real, auditoría | Fase 1 |
| **3** | Suite de tests unitarios | Cobertura completa de matriz, resiliencia, ciclo de vida | Fases 1–2 |
| **4** | Pantalla administrativa | UI en `base-admin-web` independiente de parámetros | Fase 2 |

Cada archivo de fase documenta:

1. **Qué se hizo en la fase anterior** (continuidad).
2. **Qué queda pendiente / punto de partida** para la fase que se implementa.
3. Objetivo, actividades y Definición de Done.

Los tests unitarios del núcleo y de la capa de datos se escriben **junto con**
las Fases 1 y 2. La Fase 3 **consolida y completa** la matriz de casos y la
resiliencia de punta a punta del mecanismo (sin depender aún de un caso de
negocio concreto).

### Cómo ejecutar la suite de feature flags

```bash
# Solo el mecanismo de release flags (núcleo + platform)
pytest core/tests/unit/flags/ platform/tests/unit/release/

# Equivalente con marker unit (si se filtra el resto del repo)
pytest core/tests/unit/flags/ platform/tests/unit/release/ -m unit
```

Ubicación de los tests:

| Ruta | Contenido |
|------|-----------|
| `core/tests/unit/flags/` | Evaluador, matchers, facade, matriz, resiliencia |
| `platform/tests/unit/release/` | Use cases, store Django/caché, API admin |

---

## 10. Bitácora de decisiones

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-07-03 | Release flags separadas de `core/access` y de `Parameter` | Responsabilidades distintas; evita acoplar facturación/config a liberaciones |
| 2026-07-03 | Evaluación solo dentro de la lógica de negocio (no DRF permission) | La flag no autoriza; solo elige implementación |
| 2026-07-03 | Targeting: `COMPANY`, `USER`, `COUNTRY`, `STATE`, `CITY` (sin “Zona”) | Alineado a campos existentes de `Company`; extensible vía matchers |
| 2026-07-03 | Fail → lógica antigua (`False`) | Resiliencia y reversión barata |
| 2026-07-03 | Caché híbrida BD + Redis (patrón parameters) | Cambio en caliente sin redeploy |
| 2026-07-03 | Admin en public + UI dedicada en `base-admin-web` | Operación de plataforma, no del tenant |
| 2026-07-03 | No exponer flags al cliente operativo | Backend como única fuente de verdad |
| 2026-07-03 | Tipos iniciales `RELEASE` y `OPS`; estados de ciclo de vida explícitos | Limpieza de código y kill-switch operativo |
| 2026-07-03 | Primer caso de negocio pendiente; tests del mecanismo desde el día 1 | Validar la base sin bloquear por un dominio concreto |
