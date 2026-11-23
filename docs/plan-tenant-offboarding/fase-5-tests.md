# FASE 5 — Suite de tests

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 4](fase-4-admin-web.md) · **Fase 5**

> **Continuidad.** Cada fase anterior lleva tests del camino feliz. Esta fase
> cierra la **matriz** (conflictos, no-regresión con billing y con
> `purge_unverified_tenants`, identidad global).
>
> Tests unitarios de use cases (`pytest -m unit`); API donde ya haya patrón
> en `platform/tests`.

**Objetivo:** pinchar invariantes de producto y legales-operativos para que un
cambio futuro no vuelva a usar `SUSPENDED` como baja ni borre facturas.

---

## Matriz mínima

### Cierre

- [ ] Close sobre `ACTIVE`: lifecycle `CLOSED`, `purge_after` = now + gracia.
- [ ] Close dos veces → conflicto.
- [ ] Usuarios activos → inactivos + `deactivated_by_company_close`.
- [ ] Usuarios ya inactivos → flag de cierre **false**.
- [ ] Adquisición no queda `suspended`.
- [ ] Sesiones/refresh de esos users dejan de valer.
- [ ] `public` / company inexistente → error.
- [ ] Audit emitido.

### Login

- [ ] Empresa `CLOSED` → `AUTH_019` (no `AUTH_006`, no genérico).
- [ ] Usuario baja individual, empresa `ACTIVE` → `AUTH_003`.
- [ ] Empresa `ACTIVE`, plan `suspended`, admin empresa → `billing_recovery`.
- [ ] Empresa `CLOSED` no entra a recovery aunque el plan se hubiera
      suspendido antes (invariante: close no deja recovery).

### Reopen

- [ ] Dentro de gracia, sin hold: `ACTIVE`, usuarios de cierre reactivados.
- [ ] Baja individual previa sigue inactiva.
- [ ] Fuera de gracia → conflicto.
- [ ] Con hold → conflicto.
- [ ] `PENDING_PURGE` → no reopen.

### Export / hold (Fase 2)

- [ ] Purga sin `export_attested_at` no corre.
- [ ] Waiver cuenta como attested.
- [ ] Hold omite el tenant en el queryset del job.

### Purga (Fase 3)

- [ ] Dry-run: conteos, cero mutaciones.
- [ ] Email original queda disponible (`CheckEmailAvailabilityUseCase`).
- [ ] Username original disponible.
- [ ] UUID de user sigue existiendo (tombstone).
- [ ] Invoice/Charge del tenant siguen listables.
- [ ] Schema dropeado (o fila `GONE` según Fase 0).
- [ ] Segundo run idempotente.
- [ ] Tenant `CLOSED` **con** cobro asentado **no** lo borra
      `purge_unverified_tenants`.
- [ ] Tenant unverified sin cobro **sigue** siéndolo de
      `purge_unverified_tenants` (no-regresión).

### Toggle legado

- [ ] `ToggleCompanyActive` en `ACTIVE` solo cambia suscripción
      `ACTIVE` ↔ `SUSPENDED`.
- [ ] No escribe `lifecycle`.

### Identidad “volver”

- [ ] Tras purga, un `CreateCompanyUser` / onboarding puede usar el email
      antiguo en **otra** company.
- [ ] Durante `CLOSED` (gracia), el mismo email **no** está disponible.

---

## Actividades

- [ ] Cubrir la matriz en `platform/tests/unit/company/` y
      `client/tests/unit/security/auth/`.
- [ ] Tests del job/command (`dry_run`, force, hold).
- [ ] No-regresión `test_purge_unverified_tenants.py`.
- [ ] No-regresión `test_subscription_lifecycle.py` / toggle.
- [ ] `pytest -m unit` en verde en los paths tocados.

**Definición de Done de la Fase 5:**

- [ ] La matriz de arriba está en verde.
- [ ] No hay test que asuma que “desactivar empresa” = `SUSPENDED` como baja
      contractual.
