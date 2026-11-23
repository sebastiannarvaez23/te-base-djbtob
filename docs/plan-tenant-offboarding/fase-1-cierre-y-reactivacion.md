# FASE 1 — Cierre y reactivación

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 0](fase-0-cimientos.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-export-y-cumplimiento.md)

> **Continuidad.** Requiere Fase 0 (campos y errores). Entrega el comportamiento
> reversible. **No** borra schemas ni tombstonea emails.
>
> **Fuera de esta fase:** job de purga, export completo, UI admin (Fase 4 puede
> empezar a consumir estos POST), DPA.

**Objetivo:** un admin de plataforma puede **cerrar** una empresa activa y
**reactivarla** dentro de la gracia, con sesiones cortadas, usuarios coherentes
y login que no se confunda con suspensión por cobro.

---

## Use cases

Ubicación: `platform/features/company/company/application/` (archivos
separados, un `execute()` cada uno). Repositorios por constructor.

### `CloseCompanyUseCase`

Entrada (Pydantic): `company_id`, `reason`, `actor_admin_id`.

Reglas:

- Company existe, `lifecycle == ACTIVE`, `schema_name != public`.
- No es el caso `purge_unverified` (no mezclar).
- En transacción:
  - `lifecycle = CLOSED`, `closed_at`, `purge_after = now + grace_days`.
    Si `DAYS_COMP_DEREGISTRA` es **0**, `purge_after = now` y el mismo request
    atesta export (o waiver si MinIO falla) y ejecuta `PurgeClosedCompany`
    hasta `GONE`. No hace falta el job.
  - Cerrar adquisición activa: **no** `suspended`. Preferir el mismo camino
    que cancelación de plan (`cancelled`) o un status explícito de fin de
    contrato si se añade; documentar en bitácora.
  - Usuarios de la company con `is_active=True`: `is_active=False` y
    `deactivated_by_company_close=True`. Usuarios ya inactivos: no tocar el
    flag de cierre.
  - Revocar refresh/sesiones de **todos** los usuarios de esa company
    (`revoke_session` / store existente, iterando session keys).
- Fuera o after-commit: email al admin de la empresa (plantilla nueva,
  best-effort).
- `audit_log` + `security_log` (evento de cierre).

Idempotencia: segundo close sobre `CLOSED` → error de conflicto, no reescribe
`purge_after`.

### `ReopenCompanyUseCase`

- `lifecycle == CLOSED`, `now < purge_after`, `legal_hold is False`.
- `lifecycle = ACTIVE`; anular `closed_at` / `purge_after` / `closed_reason`.
- Usuarios con `deactivated_by_company_close=True`: `is_active=True` y flag
  a `False`. Resto inactivo se queda inactivo.
- Billing: **no** reactivar en silencio un plan vencido. Si la adquisición
  quedó `cancelled` y aún no expiraba, se puede reabrir según
  `ReactivateSubscriptionUseCase`; si ya no hay vigencia, el reopen deja la
  empresa `ACTIVE` en lifecycle y el login caerá en recovery **solo si**
  producto lo autoriza. **Decisión de Fase 1:** reopen de tenant **no** implica
  `billing_recovery`. Si no hay plan activo, el admin de empresa no opera hasta
  que plataforma asigne/cobre un plan (use case de billing ya existente, llamado
  explícito o documentado como paso manual MVP).
- Auditoría.

---

## Presentation

- `POST .../companies/<uuid>/close/` body: `reason` (string, max length).
- `POST .../companies/<uuid>/reopen/` sin body o body vacío explícitamente
  permitido.
- Auth: `AdminTokenAuthentication` only.
- `@validated_body` / no `request.data` crudo.
- `wrap_response` + schemas de salida con `lifecycle`.

**Prohibido:** reutilizar `CompanyToggleActiveAPIView`.

---

## Login cliente

En `client/.../auth/infrastructure/repositories.py` (y tests de escenarios):

Tras credenciales y `user.is_active` (ojo: usuarios cerrados están inactivos →
hoy saldría `AUTH_003`). Eso **esconde** la baja de empresa.

Orden acordado:

1. Credenciales.
2. Si `user.company.lifecycle` in (`CLOSED`, `PENDING_PURGE`) → **`AUTH_019`**
   aunque `is_active` sea False por el cierre.
3. `AUTH_003` solo si la cuenta está inactiva **sin** cierre de empresa
   (baja individual).
4. Email / rol / suscripción como hoy (`AUTH_006`, recovery).

Copy `ES_OVERRIDES`: la empresa fue dada de baja; contactar a la base si es
reactivación, no “tu cuenta está inactiva” ni “empresa suspendida”.

JWT ya emitidos: al revocar refresh, el access corto muere solo; no hace falta
blacklist global en MVP.

---

## Email

Plantilla nueva (catálogo de communication, no seed en migración): aviso de
cierre al email del administrador de la empresa (rol Administrator). Si no hay
admin, log warning y no falla el cierre.

---

## Actividades

- [x] `CloseCompanyUseCase` + repo (transacción, flags de usuario, billing
      sin `suspended`).
- [x] Revocación de sesiones de todos los usuarios del tenant.
- [x] `ReopenCompanyUseCase` (gracia, hold, flags).
- [x] APIs admin close/reopen + bodies.
- [x] Gate de login `AUTH_019` vs `AUTH_003` vs `AUTH_006`.
- [x] Plantilla / envío best-effort de correo de cierre.
- [x] `audit_log` / `security_log`.
- [x] Tests unitarios del use case y de escenarios de login (Fase 5 ampliará
      la matriz; aquí los caminos felices y conflictos).

**Definición de Done de la Fase 1:**

- [x] Cerrar una empresa activa deja `CLOSED`, usuarios de cierre inactivos,
      sesiones inválidas, plan no `suspended`.
- [x] Login responde `AUTH_019`, no `AUTH_006`.
- [x] Reopen dentro de gracia restaura operación + usuarios marcados; no
      resucita bajas individuales.
- [x] Reopen fuera de gracia o con hold falla con código de conflicto.
- [x] Toggle de suspensión **sigue** funcionando en empresas `ACTIVE`.
