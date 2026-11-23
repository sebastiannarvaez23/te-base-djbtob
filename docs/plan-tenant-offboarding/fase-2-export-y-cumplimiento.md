# FASE 2 — Export, hold y cumplimiento

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 1](fase-1-cierre-y-reactivacion.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-purga.md)

> **Continuidad.** El cierre reversible ya existe. Esta fase hace **legítimo y
> trazable** conservar el schema en gracia y **borrar como encargado** después:
> export (o renuncia), legal hold, y gates alineados a políticas firmadas.
>
> **Fuera de esta fase:** redactar el markdown de privacidad/DPA (compliance CMS);
> job de drop schema (Fase 3); UI rica (Fase 4 consume attested/hold).

**Objetivo:** no purgar nunca un tenant sin constancia de devolución de datos
(o renuncia del responsable) y sin poder congelar la purga por disputa.

---

## 1. Export de tenant (encargado → responsable)

Alcance MVP: **paquete operativo** suficiente para que la empresa se lleve su
bodega, no un dump crudo de PostgreSQL al cliente final.

Mínimo razonable:

- Catálogo de referencias / UOM (lo que exista en el tenant).
- Existencias / ubicaciones.
- Pedidos y líneas en estados relevantes.
- Listado de usuarios (nombre, email, rol, activo) — son datos de la relación
  laboral del cliente; van en el export de **empresa**, no como “regalo” a
  cada titular.

Formato: archivo JSON en MinIO bajo
`base/client/tenants/<schema>/deregistration/export.json`. La purga borra el
resto del prefijo del tenant y **conserva** esa carpeta `deregistration/`.
enlace de descarga con expiración, auditoría de quién descargó.

Use case: `ExportClosedTenantUseCase` (puede correr también **justo antes** del
cierre o en `CLOSED`). Idempotente por `company_id` + día o por job id.

Si el export es pesado: Celery `TenantTask` con la conexión al schema aún
vivo.

**Renuncia:** body admin `export_waived=true` + reason → setea
`export_attested_at` sin generar archivo. Queda auditado. La purga exige
`export_attested_at` no nulo (archivo o waiver).

---

## 2. Legal hold

- `POST .../companies/<uuid>/legal-hold/` body: `enabled` bool, `reason`.
- Hold `true`: el job de Fase 3 **salta** el tenant; `ReopenCompany` del plan
  teórico también se bloquea (evitar reabrir en medio de una disputa). Si
  producto prefiere permitir reopen con hold, anotarlo en bitácora; default del
  plan: **hold bloquea reopen y purga**.
- Hold se puede originar a mano o, best-effort, si existe incidencia abierta
  del tenant (acoplar en esta fase o dejar hook + TODO testeado).

---

## 3. Políticas y DPA (ingeniería, no redacción)

Checklist para compliance (trabajo paralelo, bloquea **purga en producción**
no el merge de Fase 1):

- [ ] Publicar en `PRIVACY-POLICY` (país CO, y los que apliquen) plazos de
      gracia, encargado vs responsable, liberación de email post-purga.
- [ ] Publicar en `TERMS-AND-CONDITIONS` baja ≠ suspensión, no restore
      post-purga, quién solicita la baja.
- [ ] Alta de política `DATA-PROCESSING` (DPA) en catálogo; decidir si es
      gate de onboarding (`required_policy_codes`) o firma posterior.
- [ ] Alinear `DAYS_COMP_DEREGISTRA` al texto publicado.

Ingeniería en esta fase:

- Documentar los códigos de política en `required_codes.py` **solo** cuando
  legal confirme el DPA como obligatorio. No activar el gate de onboarding
  sin el markdown publicado (rompería altas).
- El job de purga (Fase 3) lee `export_attested_at`; no parsea markdown.

---

## 4. Constancia

Al atestar export o waiver: `export_attested_at`, `export_attested_by`,
object key si hubo archivo. Campos extra en `Company` si no se pusieron en
Fase 0.

Esto es la “acta” del MVP (fila + audit), no un PDF firmado.

---

## Actividades

- [x] Use case de export (job si aplica) + almacenamiento fuera del prefijo
      tenant.
- [x] Waiver de export + `export_attested_at`.
- [x] API legal-hold on/off.
- [x] Gate: `PurgeClosedCompany` (Fase 3) y reopen respetan hold / attested.
- [x] Lista de cláusulas mínimas entregada a quien edita políticas (este
      archivo §3 + resumen teórico §9).
- [ ] Decisión documentada sobre `DATA-PROCESSING` como required onboarding.
- [x] Tests: no attested → no purga (puede ser test del use case de purga
      mockeado o del guard compartido).

**Definición de Done de la Fase 2:**

- [x] Un tenant `CLOSED` puede exportarse o marcar waiver; queda rastro.
- [x] Hold impide reopen y queda listo para impedir purga.
- [ ] Compliance tiene la lista de textos a publicar; el código no inventa
      plazos distintos al parámetro.
