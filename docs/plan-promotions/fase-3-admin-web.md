# FASE 3 — Administración plataforma (`base-admin-web`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 2](fase-2-tests.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-client-redencion.md)

> **Continuidad — qué se hizo en las Fases 1–2.** APIs admin de vouchers en
> `base` (`/api/v1/platform/promotions/…`) y suite de tests. Esta fase
> entrega la UI operativa para crear, listar, filtrar y revocar bonos.

**Objetivo:** pestaña **Promociones** (apartado dentro de la pantalla Suscripciones)
con tabla al estilo Communications, modal de creación (simple y masivo), y servicio
HTTP en capa platform. **Sin cambios en el sidebar** (D10).

---

## Ubicación en la app

### Patrón: apartado Promociones en Suscripciones (sin submenú sidebar)

Referencia: `support-page.component.ts` (Incidencias + Feature flags). El usuario
ve **Suscripciones** en el menú; dentro de la página alterna entre **Planes** y
**Promociones**.

| Archivo | Cambio |
|---------|--------|
| `pages/subscriptions/subscriptions-page.component.ts` | `PageLayoutService` tabs: `plans` \| `promotions` |
| `pages/subscriptions/subscriptions-page.component.html` | `*ngIf` por tab |
| `components/promotions/promotions.component.ts` | Nuevo — tabla CRUD |
| `components/promotions/promotion-form-modal.component.ts` | Nuevo — crear/editar |
| `feature/platform/promotions/services/promotion-voucher.service.ts` | HTTP client |
| `feature/platform/promotions/models/promotion.interfaces.ts` | Tipos |
| `admin.module.ts` | Declarar componentes |
| `assets/i18n/es/admin.json` | `admin.subscriptions.tabs.promotions` |
| `assets/i18n/en/admin.json` | Traducciones EN |

**No** se añade ruta nueva ni ítem sidebar (D10).

---

## Servicio HTTP

```typescript
// promotion-voucher.service.ts (contrato)
getAll(params?: VoucherListParams): Observable<VoucherListResponse>
getById(id: string): Observable<PromotionVoucher>
create(body: CreateVoucherBody): Observable<PromotionVoucher>
createBulk(body: CreateBulkVouchersBody): Observable<BulkCreateResult>
revoke(id: string): Observable<PromotionVoucher>
```

Base URL: `/api/v1/platform/promotions/vouchers/`

---

## Tabla — columnas

| Columna | Tipo | Filtro |
|---------|------|--------|
| Serial | text | text |
| Tipo | badge GIFT/DISCOUNT | select |
| Alcance | text COMPANY/OPEN/FIRST_TAKE | select |
| Estado | status-badge | select |
| Empresa | text (nombre o "—") | text / autocomplete |
| Planes | muted (lista abreviada) | — |
| % / Meses | text | — |
| Vigencia redención | date range | date |
| Origen | ADMIN / PUBLIC | select |
| Creado | date | — |
| Acciones | revocar (si ACTIVE) | — |

Reutilizar:
- `wa-admin-table-shell`
- `TableConfig` de `core/interfaces/table.interfaces.ts`
- Estilos `admin-shared.*.css` + patrón `email-templates.component.ts`

---

## Modal crear bono

### Campos — modo simple

| Campo | Control | Validación |
|-------|---------|------------|
| Tipo | radio GIFT / DISCOUNT | requerido |
| Alcance | select COMPANY / OPEN / FIRST_TAKE | requerido |
| Empresa | autocomplete (si COMPANY) | requerido si scope |
| Planes | multi-select suscripciones | ≥1 |
| Meses beneficio | number (GIFT) | 1–36 |
| % descuento | number (DISCOUNT) | 1–100 |
| Duración descuento (meses) | number (DISCOUNT) | default 1 |
| Vigencia desde | datetime | |
| Vigencia hasta | datetime | > desde |
| Notas | textarea | opcional |

### Modo masivo (toggle o pestaña en modal)

| Campo | Control |
|-------|---------|
| Empresas | multi-select + checkbox "Todas las empresas existentes" |
| Resto de campos | iguales al modo simple |

Al guardar masivo → `POST …/bulk/` → toast con resumen `{ created, failed }`.

---

## Detalle / acciones

- **Ver detalle:** drawer o modal read-only con redemption history link.
- **Revocar:** `DialogService.confirm()` → `POST …/revoke/`.
- **No editar** voucher activo en MVP (solo revocar y crear nuevo).

---

## i18n

Claves sugeridas bajo `admin.promotions.*`:

- `title`, `tabs.promotions`
- `columns.*`, `filters.*`
- `types.GIFT`, `types.DISCOUNT`
- `scopes.COMPANY`, `scopes.OPEN`, `scopes.FIRST_TAKE`
- `status.ACTIVE`, `status.REDEEMED`, `status.EXPIRED`, `status.REVOKED`
- `form.*`, `bulk.*`
- `messages.created`, `messages.revoked`, `messages.bulkSummary`
- `errors.codes.PROMO_*` (sincronizado vía `errors.json`)

---

## Actividades

- [x] Refactor `SubscriptionsPageComponent` con tabs `plans` | `promotions`.
- [x] Crear `PromotionVoucherService` y modelos TS.
- [x] Implementar `PromotionsComponent` con tabla + filtros + paginación client-side o server-side según API.
- [x] Modal crear simple.
- [x] Modal/flujo bulk empresas.
- [x] Acción revocar con confirmación.
- [x] Cargar catálogo empresas (`TenantCompanyService` o existente).
- [x] Cargar catálogo suscripciones (`SubscriptionService` existente).
- [x] i18n ES + EN.
- [x] Estados loading / error / empty.
- [x] Permiso admin (hereda de ruta admin autenticada).

---

## Definición de Done — Fase 3

- [x] `/admin/subscriptions` muestra tabs Planes y Promociones.
- [ ] Listado con filtros funcional contra API real.
- [ ] Crear bono simple (GIFT y DISCOUNT) OK.
- [ ] Crear bulk 2+ empresas genera N bonos.
- [ ] Revocar bono ACTIVE actualiza tabla.
- [x] UI consistente con Communications (tabla + modal).
- [x] Sin errores de consola; textos i18n completos ES.

### Tests manuales (checklist QA)

| # | Paso | Esperado |
|---|------|----------|
| 1 | Crear GIFT OPEN | aparece en tabla ACTIVE |
| 2 | Crear DISCOUNT COMPANY | empresa en columna, email enviado |
| 3 | Bulk todas empresas | count = empresas en sistema |
| 4 | Filtrar EXPIRED | solo expirados |
| 5 | Revocar ACTIVE | estado REVOKED |
| 6 | Cambiar tab Planes | sigue funcionando card list |
