# FASE 3 — Purga (tombstone, schema, MinIO, billing)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 2](fase-2-export-y-cumplimiento.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-admin-web.md)

> **Continuidad.** Requiere ancla fiscal (Fase 0), cierre (Fase 1) y
> `export_attested_at` + hold (Fase 2). Punto de **no retorno** del schema.
>
> **Inventario de retención:** [Qué queda y qué se borra](purga-que-queda-y-que-se-borra.md).
>
> **Fuera de esta fase:** UI (Fase 4); redactar políticas.

**Objetivo:** un job idempotente que, vencida la gracia, libere identidad
global, borre datos de encargado y **conserve** evidencia de cobro y firmas.

---

## Criterio de selección

Candidatos:

- `lifecycle == CLOSED`
- `purge_after <= now`
- `legal_hold is False`
- `export_attested_at` no nulo
- `schema_name != 'public'`

**Nunca** mezclar con `purge_unverified_tenants` (criterio: users sin
`email_verified_at` y sin cobro asentado). Un tenant `CLOSED` con facturas
pagadas **sí** es candidato de **esta** purga, no de aquella.

Purga forzada (admin): mismo use case con flag `force=True` + reason; igual
exige hold off y attested (salvo waiver). No salta retención fiscal.

---

## `PurgeClosedCompanyUseCase`

Un company por invocación. El task itera ids.

Al tomar el trabajo: `lifecycle = PENDING_PURGE` (evita doble job).

Orden (ajustar al ancla fiscal de Fase 0):

1. Snapshot fiscal / `ClosedTenantRecord` + SET_NULL o desvío de FKs de
   `Invoice`/`Charge` según diseño.
2. Integraciones: borrar secretos tenant / desactivar conexiones (best-effort
   log si el módulo no está desplegado).
3. Tombstone de **todos** los `User` de la company:
   - `email` → `closed_<uuid>@tombstone.invalid` (unique)
   - `username` → `closed_<uuid>` (unique, longitud)
   - Vaciar teléfono, documento, nombres si se acuerda minimización; como
     mínimo identificadores únicos y `picture`
   - `set_unusable_password()`
   - `is_active=False`, `deactivated_by_company_close` irrelevante ya
   - Borrar 2FA, trusted devices, recovery/confirmation tokens, preferencias
     opcionales
   - No borrar la fila (UUID, firmas `subject_id`)
4. Vaciar `Company.nit` (libera unique condicional) **después** de copiarlo
   al ancla fiscal.
5. MinIO: borrar prefijo `client/tenants/<schema>/` **excepto**
   `deregistration/` (export de baja).
6. `DROP SCHEMA` via `company.delete(force_drop=True)` **o** drop schema
   manteniendo fila `GONE` (opción 2 de Fase 0).
7. Dominios: CASCADE o borrar explícito.
8. Certificado de borrado: log estructurado + fila
   (`purged_at`, conteos: users tombstoned, schema dropped).
9. Email best-effort al último admin conocido (el email ya es tombstone: usar
   el destinatario del export/waiver o no enviar PII). Preferible: notificar
   solo a plataforma.

Fallo a mitad: `PENDING_PURGE` + log; **no** dejar schema dropeado y users
sin tombstone, ni al revés. Preferir tombstone **antes** del drop. Reintento
idempotente: users ya `closed_*` se saltan; schema ausente se considera hecho.

---

## Qué **no** se borra

- `Invoice`, `Charge`, intentos, webhooks de cobro (ancla fiscal).
- `PolicySignature` (append-only). El `tenant_id` queda como string histórico.
- `ClosedTenantRecord` / snapshots.
- Admins de plataforma.

---

## Transporte

- Celery task `company.purge_closed_tenants` (mismo estilo que
  `onboarding.purge_unverified_tenants`: task delgado, lógica en use case).
- `python manage.py purge_closed_tenants [--dry-run] [--company-id=]`
- Beat: diario.

---

## Actividades

- [x] Guardas: gracia, hold, attested, no mezclar con unverified purge.
- [x] Tombstone de usuarios + limpieza de auth satélite.
- [x] Liberación de NIT + ancla fiscal.
- [x] Borrado MinIO del prefijo tenant.
- [x] Drop schema / fila según Fase 0.
- [x] Task + management command + dry-run.
- [x] Certificado (log + persistencia mínima).
- [x] Tests unitarios: hold no purga, sin export no purga, dry-run no muta,
      segundo run sobre `GONE` es idempotente.

**Definición de Done de la Fase 3:**

- [ ] Tras purga, `CheckEmailAvailabilityUseCase` devuelve libre para el
      email original.
- [ ] Una factura pagada previa sigue consultable en admin billing.
- [ ] El schema del tenant no existe.
- [x] `purge_unverified_tenants` no selecciona (ni rompe) un `CLOSED` con
      cobro.
- [x] Dry-run no muta.
