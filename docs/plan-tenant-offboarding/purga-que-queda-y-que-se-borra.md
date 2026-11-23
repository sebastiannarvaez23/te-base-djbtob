# Qué borra y qué conserva la purga de empresa

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · [Fase 3 — Purga](fase-3-purga.md)

Documento de referencia operativa. No es dictamen jurídico. Describe el
comportamiento **actual** del código (cierre → gracia → purga) para saber qué
desaparece del producto y qué queda como evidencia.

---

## 1. Dos momentos distintos

| Momento | Estado | Qué pasa |
|---------|--------|----------|
| **Cierre** (`dar de baja`) | `CLOSED` | Se corta el acceso operativo. El schema, MinIO y las cuentas **siguen existiendo** durante la gracia (`DAYS_COMP_DEREGISTRA`). Se puede reactivar. |
| **Purga** | `PENDING_PURGE` → `GONE` | Punto de no retorno. Se borra la bodega, se anonimizan cuentas y se conserva lo fiscal. No hay restore del schema. |

Si `DAYS_COMP_DEREGISTRA = 0`, cierre + export + purga ocurren en el mismo
POST. La empresa pasa a `GONE` de inmediato.

Los listados operativos de **empresas** y **usuarios** (admin y cliente)
**no incluyen** tenants `GONE` ni usuarios tombstone. Una empresa `CLOSED`
sí aparece mientras dura la gracia (reactivación, export, hold).

---

## 2. Qué se borra en la purga

### Schema PostgreSQL del tenant

`DROP SCHEMA` de todo lo operativo de bodega, entre otros:

- Catálogo de referencias / UOM
- Existencias, ubicaciones, balances
- Pedidos, líneas, picking, packing, recepción, despachos, devoluciones
- Configuración WMS del tenant
- Cualquier otra tabla que viva en el schema de la empresa

Eso **no se puede recuperar**. El export previo no es un dump completo (ver §4).

### MinIO (`bucket base`)

Se borra el prefijo `client/tenants/<schema>/` **excepto**
`deregistration/`:

- Fotos de perfil
- Ilustraciones de referencias
- Cualquier otro objeto bajo el tenant

**Se conserva** `client/tenants/<schema>/deregistration/export.json`.

### Identidad de usuarios (schema público)

Las filas **no se eliminan** (el UUID permanece por firmas e historial).
Se **anonimizan**:

| Campo | Destino |
|-------|---------|
| `email` | `closed_<uuid>@tombstone.invalid` |
| `username` | `closed_<uuid>` |
| Nombres, teléfono, documento, foto | Vacíos |
| Password | Inutilizable |
| `is_active` | `false` |

Se borran tokens de confirmación/recuperación y dispositivos de confianza.
El email y usuario originales quedan **libres** para un onboarding nuevo.

### Empresa (fila `companies`)

- `lifecycle = GONE`
- `nit` vacío (libera el unique condicional)
- El schema ya no existe; la fila se queda como ancla mínima

---

## 3. Qué se conserva

| Dato | Dónde | Para qué |
|------|-------|----------|
| Export operativo | MinIO `client/tenants/<schema>/deregistration/export.json` | Portabilidad / constancia de devolución |
| Fila de empresa `GONE` | `companies` | No reusar schema a ciegas; fechas de cierre/purga |
| Ancla fiscal | `closed_tenant_records` | NIT, razón social, schema, `purged_at`, usuarios tombstoneados |
| Facturas y cobros | `Invoice`, `Charge` | Deber tributario. FK a empresa en `SET_NULL`; quedan `tenant_nit` y `tenant_name` |
| Firmas de políticas | `PolicySignature` | Evidencia append-only (`tenant_id` como string) |
| UUID de usuario | `security_users` | No romper `subject_id` de firmas; ya no sirven para login |
| Admins de plataforma | `admin_users` | No se tocan |
| Historial de suscripción | `CompanySubscription` (cancelada) | Relación comercial |

**Regla corta:** la bodega se devuelve y se borra; la cuenta se anonimiza;
la factura se conserva.

---

## 4. Qué lleva el `export.json` (MVP)

No es un backup cifrado ni un dump de PostgreSQL. Paquete operativo acotado:

- Empresa: `id`, nombre, NIT, schema
- Usuarios: `id`, email, username, nombre, rol, activo
- Bodega: referencias (`código`, `nombre`, `estado`) y pedidos (`número`,
  `estado`), tope 5 000 filas cada uno

**No** incluye existencias, movimientos, ubicaciones, picking, packing ni
archivos de MinIO. El backup cifrado en el correo de baja está **diferido**.

Ruta:

```
base/client/tenants/<schema>/deregistration/export.json
```

Ejemplo: `base/client/tenants/arisoft-sas/deregistration/export.json`.

---

## 5. Listados después de la purga

| Superficie | `ACTIVE` | `CLOSED` (gracia) | `GONE` (purgada) |
|------------|----------|-------------------|------------------|
| Listado de empresas (admin) | Sí | Sí | No |
| Listado de usuarios tenant (admin) | Sí | Sí (desactivados) | No |
| Usuarios WMS de la empresa | Sí | Sí, sin tombstones | N/A (sin acceso) |
| Detalle / APIs de cierre por UUID | Sí | Sí | Sí (soporte / fiscal, no directorio) |

Filtro de lifecycle en el listado: `ACTIVE`, `CLOSED`, `PENDING_PURGE`.
`GONE` no es un filtro de directorio.

---

## 6. Qué no cubre este flujo

- Restore del schema después de `GONE`
- Canal ARCO de una persona con la empresa aún activa
- Borrado de admins de plataforma
- Mezclar con `purge_unverified_tenants` (onboardings nunca confirmados)
