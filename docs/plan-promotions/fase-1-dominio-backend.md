# FASE 1 — Dominio backend y APIs

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-tests.md)

> **Continuidad — punto de partida.** Es la **primera fase de construcción**. No
> existe dominio de promociones en el repo. Prerequisitos: stack de billing
> (`subscription`, `payments`, `invoice`), onboarding
> (`client/features/security/onboarding/`), plantillas de email
> (`platform/features/communication/`), y catálogo de empresas en schema
> `public`.
>
> **Qué queda explícitamente fuera de esta fase:** UI admin (Fase 3), UI cliente
> (Fase 4), compra pública (Fase 5). Esta fase entrega APIs y lógica consumible
> por esos frontends.

**Objetivo:** implementar el bounded context `platform/features/billing/promotion/`
con modelos, use cases, APIs admin/tenant/preview, integración mínima con
cobros/renovaciones, envío de emails para bonos dedicados a empresa, y job de
expiración.

---

## Estructura objetivo

```
platform/features/billing/promotion/
├── models.py
├── apps.py
├── domain/
│   ├── schemas.py
│   └── interfaces.py
├── application/
│   ├── use_cases/
│   │   ├── create_voucher.py
│   │   ├── create_bulk_vouchers.py
│   │   ├── validate_voucher.py
│   │   ├── redeem_voucher.py
│   │   ├── revoke_voucher.py
│   │   ├── list_vouchers.py
│   │   └── expire_vouchers.py
│   ├── pricing.py              # calcular monto post-bono
│   └── benefit_manager.py      # PromotionBenefit activo
├── infrastructure/
│   └── repositories.py
├── presentation/
│   ├── api.py
│   ├── public_api.py           # validate preview (onboarding anónimo)
│   ├── serializers.py
│   ├── bodies.py
│   └── urls.py
├── tasks/
│   └── expiry.py
└── migrations/
```

---

## Modelos (schema `public`)

### `PromotionVoucher`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | UUID PK | |
| `serial` | CharField unique | Índice CI |
| `voucher_type` | Enum `GIFT` \| `DISCOUNT` | |
| `scope` | Enum `COMPANY` \| `OPEN` \| `FIRST_TAKE` | |
| `origin` | Enum `ADMIN` \| `PUBLIC_PURCHASE` | |
| `status` | Enum `ACTIVE` \| `REDEEMED` \| `EXPIRED` \| `REVOKED` | |
| `company_id` | FK Company nullable | Solo `COMPANY` |
| `discount_percent` | Decimal nullable | Solo `DISCOUNT` |
| `benefit_months` | PositiveSmallInt nullable | Solo `GIFT` |
| `discount_duration_months` | PositiveSmallInt default 1 | Solo `DISCOUNT` |
| `redeem_valid_from` | DateTime | |
| `redeem_valid_until` | DateTime | |
| `subscriptions` | M2M → `Subscription` | Planes aplicables |
| `created_by` | FK admin user nullable | |
| `notes` | TextField blank | |
| `metadata` | JSONField | Compra pública: comprador, destinatario |
| `created_at` / `updated_at` | | |

### `PromotionRedemption`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | UUID PK | |
| `voucher_id` | FK | |
| `company_id` | FK | |
| `redeemed_at` | DateTime | |
| `context` | Enum `ONBOARDING` \| `SETTINGS` \| `PUBLIC_PURCHASE` | |
| `subscription_id` | FK | Plan aplicado |
| `original_amount` | Decimal | |
| `final_amount` | Decimal | |
| `discount_amount` | Decimal | |
| `idempotency_key` | CharField unique nullable | |

### `PromotionBenefit` (beneficio activo post-redención)

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | UUID PK | |
| `company_id` | FK | |
| `redemption_id` | FK OneToOne | |
| `voucher_type` | Enum | |
| `subscription_id` | FK | Plan durante beneficio |
| `previous_subscription_id` | FK nullable | Para revert gift superior |
| `benefit_start` | DateTime | |
| `benefit_end` | DateTime | |
| `discount_percent` | Decimal nullable | |
| `remaining_discount_cycles` | Int nullable | |
| `status` | Enum `ACTIVE` \| `COMPLETED` \| `CANCELLED` | |

---

## Códigos de error (`PROMO_*`)

| Código | HTTP | Descripción |
|--------|------|-------------|
| `PROMO_001` | 404 | Serial no encontrado |
| `PROMO_002` | 400 | Bono no activo (redeemed/expired/revoked) |
| `PROMO_003` | 400 | Plan no elegible / inferior al actual |
| `PROMO_004` | 400 | Fuera de vigencia de redención |
| `PROMO_005` | 403 | Alcance no permite esta empresa |
| `PROMO_006` | 409 | Bono ya consumido (`FIRST_TAKE` o doble redención) |
| `PROMO_007` | 400 | Tipo de bono incompatible con operación |
| `PROMO_008` | 409 | Idempotencia — redención ya procesada |
| `PROMO_009` | 400 | Validación de entrada (%, meses, fechas) |
| `PROMO_010` | 500 | Error interno best-effort (no usar en flujo feliz) |
| `PROMO_011` | 409 | Empresa ya tiene un beneficio de bono activo |

Añadir traducciones ES en `core/errors/sync_i18n.py` y ejecutar `syncerrors`.

---

## Use cases

### `CreateVoucherUseCase`

- Input: tipo, scope, empresa (opcional), planes, %, meses, vigencia redención.
- Genera serial único.
- Persiste `ACTIVE`.
- Si `scope=COMPANY` → dispara email (`GIFT_VOUCHER` / `DISCOUNT_VOUCHER`).

### `CreateBulkVouchersUseCase`

- Input: lista de `company_ids` o flag `all_companies=true`.
- Por cada empresa → `CreateVoucherUseCase` (transacción por empresa).
- Retorna resumen `{ created: N, failed: [...] }`.

### `ValidateVoucherUseCase`

- Input: `serial`, `company_id?`, `subscription_id?`, `context`.
- No muta estado.
- Retorna preview: tipo, monto original, monto final, meses beneficio, mensajes.

### `RedeemVoucherUseCase`

- Valida → verifica **sin beneficio activo** (`PROMO_011`) → crea
  `PromotionRedemption` → marca voucher `REDEEMED` → crea `PromotionBenefit` →
  aplica efecto en `CompanySubscription` (o deja pendiente en onboarding hasta finalize).
- Idempotente por `idempotency_key`.

### `RevokeVoucherUseCase`

- Solo `ACTIVE` → `REVOKED`.

### `ExpireVouchersUseCase`

- Batch: `ACTIVE` + `redeem_valid_until < now()` → `EXPIRED`.

---

## APIs

Registrar en `base/urls.py` y `base/urls_public.py` según corresponda.

### Admin (`IsPlatformAdmin`)

| Método | Ruta | Acción |
|--------|------|--------|
| `GET` | `/api/v1/platform/promotions/vouchers/` | Listar con filtros |
| `POST` | `/api/v1/platform/promotions/vouchers/` | Crear uno |
| `POST` | `/api/v1/platform/promotions/vouchers/bulk/` | Crear masivo |
| `GET` | `/api/v1/platform/promotions/vouchers/<id>/` | Detalle |
| `POST` | `/api/v1/platform/promotions/vouchers/<id>/revoke/` | Revocar |
| `GET` | `/api/v1/platform/promotions/redemptions/` | Historial redenciones |

### Tenant (`IsCompanyMember`)

| Método | Ruta | Acción |
|--------|------|--------|
| `POST` | `/api/v1/promotions/validate/` | Preview redención |
| `POST` | `/api/v1/promotions/redeem/` | Redimir en settings |

### Onboarding (cookie session, sin JWT)

| Método | Ruta | Acción |
|--------|------|--------|
| `POST` | `/api/v1/onboarding/promotions/validate/` | Preview en wizard |
| `POST` | `/api/v1/onboarding/promotions/apply/` | Reservar bono en sesión onboarding |

Extender `OnboardingState` / `payment_data` con `applied_voucher_serial`,
`adjusted_price`, `promotion_preview`.

### Público (fase 5 — stub en Fase 1)

| Método | Ruta | Acción |
|--------|------|--------|
| `POST` | `/api/v1/public/promotions/purchase/preview/` | Precio catálogo regalo |
| `POST` | `/api/v1/public/promotions/purchase/checkout/` | Placeholder 501 hasta Fase 5 |

---

## Integración billing

**Actividades:**

- [ ] Extender `charge_plan()` / `CreateChargeUseCase` para `adjusted_amount` y
      metadata `promotion_redemption_id`.
- [ ] Extender `invoice_context.py`: `original_amount`, `discount_amount`,
      **anexo bono** (`promotion_serial`, `voucher_type`, `discount_percent`).
- [ ] `ChangeSubscriptionUseCase`: gift plan superior → `PromotionBenefit` +
      `previous_subscription_id`; programar reversión.
- [ ] `renew_subscription`: si `PromotionBenefit` gift activo → skip charge; si
      discount activo → aplicar % y decrementar `remaining_discount_cycles`.
- [ ] Job `revert_gift_subscription`: al `benefit_end`, restaurar plan anterior.
- [ ] Onboarding `finalize`: **siempre** persistir `PaymentMethod` desde
      `payment_data`; ejecutar charge con monto ajustado (puede ser $0); redimir
      bono aplicado en sesión.

---

## Emails

- [ ] Seed documentado (no fixture obligatorio) para plantillas `GIFT_VOUCHER`,
      `DISCOUNT_VOUCHER` con `mock_data` de ejemplo.
- [ ] Dispatcher `dispatch_company_voucher_email(voucher)` best-effort.
- [ ] Context builder: serial, plan, vigencia, %, meses.

---

## Celery / management

- [ ] Task `expire_promotion_vouchers` (diario).
- [ ] Task `revert_expired_gift_benefits` (diario).
- [ ] `python manage.py expire_promotion_vouchers` para ejecución manual.

---

## Actividades checklist

- [ ] Crear app `promotion` bajo `platform/features/billing/`.
- [ ] Modelos + migraciones en schema `public`.
- [ ] Interfaces de repositorio + `DjangoPromotionVoucherRepository`.
- [ ] Use cases listados arriba.
- [ ] Códigos `PROMO_*` + `syncerrors`.
- [ ] APIs admin + tenant + onboarding.
- [ ] `audit_log` en create/revoke/redeem.
- [ ] Integración billing (cobro, renovación, factura).
- [ ] Emails empresa dedicada.
- [ ] Tasks expiry + revert.
- [ ] Registrar app en `INSTALLED_APPS` (SHARED_APPS).
- [ ] Documentar variables si aplica (`PROMO_SERIAL_PREFIX=WLGX`).

---

## Definición de Done — Fase 1

- [ ] CRUD admin de vouchers funcional vía API (curl/Postman).
- [ ] Validar + redimir gift/discount en tenant con empresa existente.
- [ ] Onboarding aplica bono y finalize respeta monto ajustado.
- [ ] Bonos `COMPANY` disparan email (mock en dev).
- [ ] Job marca `EXPIRED` correctamente.
- [ ] Gift superior revierte al plan anterior al fin de beneficio.
- [ ] Tests de Fase 2 pueden ejecutarse (aunque aún no estén todos verdes).

### Archivos principales (referencia)

| Archivo | Rol |
|---------|-----|
| `platform/features/billing/promotion/models.py` | Persistencia |
| `platform/features/billing/promotion/application/use_cases/*.py` | Lógica |
| `platform/features/billing/promotion/presentation/api.py` | HTTP admin/tenant |
| `platform/features/billing/subscription/application/charging.py` | Hook cobro |
| `client/features/security/onboarding/application/use_cases/finalize.py` | Hook registro |
