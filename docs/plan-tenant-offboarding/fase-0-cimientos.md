# FASE 0 — Cimientos (estado de empresa, parámetros, errores)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 0** · Siguiente → [Fase 1](fase-1-cierre-y-reactivacion.md)

> **Continuidad.** Primera fase de construcción. Prerequisito: el
> [resumen teórico](00-resumen-teorico.md). No hay bounded context nuevo: se
> extiende `platform/features/company/company/` y se prepara el ancla fiscal
> para que la Fase 3 pueda borrar el tenant sin perder facturas.
>
> **Fuera de esta fase:** use cases de cierre/purga, UI, job Celery, export,
> redacción de políticas.

**Objetivo:** que `Company` tenga un ciclo de vida propio, independiente de
`CompanySubscription.status`, con parámetros de gracia, códigos de error y un
diseño de persistencia que permita conservar cobros cuando la fila tenant
desaparezca.

---

## Modelo `Company` (schema `public`)

Campos nuevos (migración **solo esquema**, sin seed):

| Campo | Tipo | Notas |
|-------|------|-------|
| `lifecycle` | CharField / TextChoices | `ACTIVE` \| `CLOSED` \| `PENDING_PURGE`. Default `ACTIVE` |
| `closed_at` | DateTimeField null | Set al cerrar; null si activa |
| `purge_after` | DateTimeField null | `closed_at` + gracia; null si activa |
| `closed_reason` | CharField / Text | Motivo de plataforma (longitud máxima) |
| `closed_by_admin_id` | UUID null | Admin de plataforma; sin FK rígida a `admin_users` si se quiere sobrevivir a bajas de staff, o `DO_NOTHING` |
| `legal_hold` | BooleanField default False | Bloquea purga y, si se acuerda, también reopen |
| `legal_hold_reason` | CharField blank | |
| `export_attested_at` | DateTimeField null | Constancia Fase 2; columna reservada ya en Fase 0 |

Índice sugerido: `(lifecycle, purge_after)` para el job.

**No** añadir `is_active` en `Company`. El listado admin hoy deriva
`is_active` de la suscripción: hay que **separar** en el schema de salida:

- `subscription_active` (plan)
- `lifecycle` (tenant)

El toggle actual sigue mutando solo la adquisición.

---

## Ancla fiscal (diseño obligatorio aquí, implementación mínima)

Problema: `Invoice` / `Charge` / adquisiciones apuntan a `Company` (varios
`CASCADE` / `DO_NOTHING`). La purga no puede borrar evidencia de cobro.

Entregable de esta fase: **decisión implementada en esquema**, una de:

1. **Recomendada:** tabla `ClosedTenantRecord` (id, company_id original, nit,
   name, schema_name, closed_at, purged_at) + en `Invoice`/`Charge` campos
   snapshot (`tenant_nit`, `tenant_name`) ya usables hoy, y FK a Company
   `SET_NULL` **solo cuando** se ejecute la purga (Fase 3). Fase 0 añade
   columnas snapshot y la tabla vacía.
2. Alternativa: nunca borrar la fila `companies`, marcar `GONE` y drop solo
   del schema tenant. Más simple para FKs; el NIT hay que liberarlo igual
   (vaciar + unique condicional ya existe).

Documentar la opción elegida en la bitácora del resumen teórico al
implementar. Preferir (1) si se quiere reutilizar `schema_name`; (2) si se
quiere menos riesgo en cobros.

---

## Usuarios: marca de cierre

En `registration.User` (o tabla satélite 1:1, si se quiere no inflar el
modelo de auth):

| Campo | Tipo | Notas |
|-------|------|-------|
| `deactivated_by_company_close` | bool default False | Permite reactivar solo a quienes apagó el cierre, no bajas individuales |

Migración de esquema; default `False` es estructural, no seed de negocio.

---

## Parámetros de plataforma

Nuevo parámetro (vía catálogo existente `Parameter`, **no** en migración):

- Código `DAYS_COMP_DEREGISTRA`, default **30**, activo.

El valor se lee en `CloseCompany` para calcular `purge_after`. **0** significa
purga inmediata en el mismo request de baja (export + tombstone + drop de
schema), sin esperar el job. Alinear con el texto CO de privacidad (Fase 2).

Opcional mismo patrón: `TENANT_CLOSE_EXPORT_REQUIRED` (bool) para el gate de
Fase 2.

---

## Errores

Familia nueva o extensión de `core/errors/domains/tenant.py` / `auth.py`:

| Código | Uso |
|--------|-----|
| `AUTH_019` (propuesta) | Empresa dada de baja (`CLOSED` / `PENDING_PURGE`); no es `AUTH_006` |
| `CO_xxx` | Empresa ya cerrada; no se puede cerrar dos veces |
| `CO_xxx` | No se puede reactivar (fuera de gracia, hold, o lifecycle incorrecto) |
| `CO_xxx` | Purga bloqueada por hold / falta de constancia de export |

Inglés en `ERROR_REGISTRY`, español en `ES_OVERRIDES`, luego
`python manage.py syncerrors`. Copy de plataforma: qué pasó y qué hacer, sin
UUID.

Todavía no cablear el login (eso es Fase 1); en Fase 0 basta el código
registrado.

---

## Listados y schemas Pydantic

- `CompanyListItemSchema` / detalle: exponer `lifecycle`, `closed_at`,
  `purge_after`, `legal_hold` además del `is_active` de suscripción
  (renombrar en API con cuidado o añadir campos sin romper clientes: preferir
  **añadir** `lifecycle` y dejar `is_active` como “plan activo” hasta Fase 4).
- Interfaces de repositorio: `get_lifecycle`, sin lógica de cierre todavía.

---

## Actividades

- [x] Añadir `lifecycle` + timestamps/hold/export_attested_at a `Company`
      (migración de esquema).
- [x] Backfill estructural: todas las filas existentes `lifecycle=ACTIVE`
      (único backfill admisible: valor por defecto de la columna nueva).
- [x] Campo `deactivated_by_company_close` en usuarios cliente.
- [x] Diseñar e implementar columnas/tabla de ancla fiscal (opción 1 o 2).
- [x] Registrar parámetro `DAYS_COMP_DEREGISTRA` vía flujo de parámetros
      existente (no seed en migración).
- [x] Códigos de error + `ES_OVERRIDES` + `syncerrors`.
- [x] Extender schemas/listados de company **sin** cambiar
      `toggle_active`.
- [x] Tests unitarios del modelo/constraints y del default de lifecycle.
- [x] Anotar en la bitácora la opción de ancla fiscal elegida.

**Definición de Done de la Fase 0:**

- [x] `Company` tiene ciclo de vida persistido; empresas actuales `ACTIVE`.
- [x] El toggle de suscripción **sigue** comportándose igual (test de no
      regresión).
- [x] Hay un diseño de esquema que permite facturas sin FK viva a un tenant
      dropeado (o `GONE` sin drop de fila).
- [x] Errores nuevos existen en registry; el login emite `AUTH_019` en Fase 1.
