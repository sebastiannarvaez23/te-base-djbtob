# FASE 4 — Administración plataforma (`base-admin-web`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 3](fase-3-purga.md) · **Fase 4** · Siguiente → [Fase 5](fase-5-tests.md)

> **Continuidad.** Consume APIs de Fases 1–3. El listado de empresas **ya**
> tiene un interruptor que suspende el plan: **no se reutiliza** para la baja.
>
> **Fuera de esta fase:** autoservicio en `base-client-web`; ARCO de persona;
> redactar políticas (solo enlaces / copy de UI).

**Objetivo:** que un admin de la base pueda dar de baja, ver la gracia,
reactivar, atestar export/hold y (si aplica) disparar purga, sin confundir
con “empresa suspendida por cobro”.

---

## UI actual a no mezclar

En `tenant-companies`: el toggle llama `toggleTenant` →
`CompanyToggleActiveAPIView`. Debe permanecer como **suspender/reactivar
plan**. Copy: no decir “dar de baja”.

Nueva acción (menú o botón danger, no el mismo icono `bx-toggle`):

- **Dar de baja empresa** → diálogo de confirmación (`wa-dialog` /
  `DialogService`) con motivo (`wa-form-field`), resumen de efectos (usuarios
  sin acceso, datos retenidos X días, no es suspensión).
- Controles de librería: `wa-btn`, `wa-form-field`; **no** `<button>` /
  `<select>` nativos.

---

## Superficies

1. **Listado / detalle de empresas**
   - Badge de `lifecycle` distinto del badge de suscripción
     (`CLOSED`, `PENDING_PURGE` vs plan `suspended`).
   - Reloj: “Purga el {{purge_after}}”.
   - Acciones según estado:
     - `ACTIVE`: Dar de baja; Suspender plan (toggle existente).
     - `CLOSED`: Reactivar (si gracia y no hold); Hold; Export / waiver;
       Purga anticipada (peligro, doble confirmación).
     - `PENDING_PURGE`: solo lectura. `GONE` no aparece en el listado (fila fiscal en `closed_tenant_records`).

2. **Usuarios del tenant** (`tenant-users`)
   - Con empresa `CLOSED`: read-only o aviso; el toggle individual no debe
     “reactivarse” saltándose `ReopenCompany`.
   - Tras purga (`GONE`): el listado de empresas y el de usuarios **no**
     incluyen el tenant ni sus tombstones. Evidencia fiscal en
     `closed_tenant_records`.

3. **i18n** `admin.json` es/en: cierre, gracia, hold, export, errores de
   `errors.json` vía `syncerrors`.

4. **Permisos:** diferir gates reales según regla de workspace; mocks
   temporales si el resto de módulos operativos aún no cerraron el pase de
   permisos. No inventar un feature flag de baja como bloqueo “de paso”.

---

## Cliente WMS (`base-client-web`) — mínimo

No es el foco de esta fase. Solo verificar que el login muestra `AUTH_019`
(traducción ya en `errors.json`). No pantalla de “quiero volver” en MVP.

---

## Actividades

- [x] Copy y badge de lifecycle ≠ suspensión.
- [x] Diálogo de cierre (motivo + confirmación) → `POST close`.
- [x] Reactivar → `POST reopen`.
- [x] Hold on/off.
- [x] Export / waiver (descarga o constancia).
- [x] Purga anticipada (si el backend la expone) con confirmación fuerte.
- [x] No usar HTML nativo de interacción.
- [ ] Verificar en UI el flujo (listado ACTIVE → CLOSED → reopen) además del
      badge.

**Definición de Done de la Fase 4:**

- [ ] Un admin puede cerrar y reactivar sin pasar por el toggle de plan.
- [ ] El toggle de plan en una empresa `ACTIVE` sigue suspendiendo cobro
      (`SUSPENDED` + recovery), no pone `CLOSED`.
- [ ] Estados `CLOSED` se entienden en la tabla (gracia visible).
- [ ] Login cliente con empresa cerrada muestra el mensaje de baja, no el de
      suspensión.
