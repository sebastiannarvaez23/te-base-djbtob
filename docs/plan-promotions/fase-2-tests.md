# FASE 2 — Suite de tests (matriz exhaustiva)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 1](fase-1-dominio-backend.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-admin-web.md)

> **Continuidad — qué se hizo en la Fase 1.** Dominio `promotion`, modelos,
> use cases, APIs, hooks de billing, emails y jobs. La Fase 2 **no añade
> producto nuevo:** consolida calidad con una matriz de pruebas exhaustiva que
> cubra creación, validación, redención, expiración, billing y resiliencia.

**Objetivo:** cobertura unitaria, de integración y API del core de promociones,
sin depender de frontends. Toda regla de negocio del [resumen teórico](00-resumen-teorico.md)
debe tener al menos un caso automatizado.

---

## Ubicación de tests

```
platform/tests/unit/billing/promotion/
├── conftest.py                    # fixtures: planes, empresas, vouchers
├── test_serial_generator.py
├── test_create_voucher.py
├── test_create_bulk_vouchers.py
├── test_validate_voucher.py
├── test_redeem_voucher_gift.py
├── test_redeem_voucher_discount.py
├── test_voucher_scope.py
├── test_voucher_expiry.py
├── test_revoke_voucher.py
├── test_pricing.py
├── test_benefit_manager.py
├── test_idempotency.py
├── test_email_dispatch.py
└── test_evaluation_matrix.py      # tabla maestra PROMO_*

platform/tests/integration/billing/promotion/
├── conftest.py
├── test_repository.py
├── test_redeem_with_subscription.py
├── test_gift_upgrade_revert.py
├── test_renewal_skip_gift.py
├── test_renewal_discount.py
├── test_onboarding_apply.py
└── test_expire_job.py

platform/tests/api/billing/promotion/
├── test_admin_voucher_api.py
├── test_tenant_redeem_api.py
├── test_onboarding_promo_api.py
└── test_public_purchase_api.py    # fase 5 — skip hasta implementar

client/tests/unit/onboarding/
└── test_onboarding_promotion_step.py

client/tests/integration/onboarding/
└── test_finalize_with_voucher.py
```

Marcar con `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.api`.

---

## Convenciones de fixtures

| Fixture | Descripción |
|---------|-------------|
| `plan_basic` | Subscription price=50 |
| `plan_pro` | Subscription price=100 |
| `plan_enterprise` | Subscription price=200 |
| `company_a`, `company_b` | Tenants de prueba |
| `voucher_gift_pro_open` | GIFT, OPEN, Pro, 3 meses beneficio |
| `voucher_discount_pro_20` | DISCOUNT 20%, Pro, 1 mes descuento |
| `voucher_gift_company_a` | GIFT dedicado a company_a |
| `voucher_first_take` | FIRST_TAKE, DISCOUNT 50%, cualquier plan |
| `active_benefit_gift` | PromotionBenefit activo post-redención |

---

## A. Creación de bonos (admin)

### A.1 — `CreateVoucherUseCase`

| ID | Escenario | Entrada | Esperado |
|----|-----------|---------|----------|
| A1.1 | Gift mínimo válido | GIFT, OPEN, [Pro], benefit_months=3, vigencia futura | `ACTIVE`, serial único `WLGX-GFT-*` |
| A1.2 | Discount mínimo válido | DISCOUNT, 15%, [Basic, Pro], duration=1 | `ACTIVE`, serial `WLGX-DSC-*` |
| A1.3 | Company dedicado | GIFT, COMPANY, company_a | `company_id` set; email disparado |
| A1.4 | FIRST_TAKE | DISCOUNT, FIRST_TAKE, sin company | `company_id=null`, scope correcto |
| A1.5 | Múltiples planes | GIFT, [Basic, Pro, Enterprise] | M2M con 3 suscripciones |
| A1.6 | benefit_months = 0 | GIFT | `PROMO_009` |
| A1.7 | benefit_months > 36 | GIFT | `PROMO_009` (límite configurable) |
| A1.8 | discount_percent = 0 | DISCOUNT | `PROMO_009` |
| A1.9 | discount_percent = 101 | DISCOUNT | `PROMO_009` |
| A1.10 | Sin planes | cualquier tipo | `PROMO_009` |
| A1.11 | redeem_valid_until < redeem_valid_from | fechas invertidas | `PROMO_009` |
| A1.12 | redeem_valid_until en el pasado | | `PROMO_009` o warning según regla |
| A1.13 | Serial colisión (mock) | generador devuelve duplicado | reintento / error controlado |
| A1.14 | COMPANY sin company_id | | `PROMO_009` |
| A1.15 | OPEN con company_id | | `PROMO_009` |
| A1.16 | Notas y metadata | texto libre | persistidos |
| A1.17 | audit_log | create exitoso | evento registrado |

### A.2 — `CreateBulkVouchersUseCase`

| ID | Escenario | Entrada | Esperado |
|----|-----------|---------|----------|
| A2.1 | Dos empresas | [company_a, company_b] | 2 vouchers, seriales distintos |
| A2.2 | Todas las empresas | `all_companies=true` | N = count empresas existentes |
| A2.3 | Todas — snapshot | crear empresa después | nueva empresa **sin** bono |
| A2.4 | Lista vacía | [] | `PROMO_009` |
| A2.5 | Empresa inexistente en lista | UUID inválido | error parcial en resumen |
| A2.6 | Misma config todos | bulk gift 6 meses | todos mismos benefit_months |
| A2.7 | Email por empresa | bulk COMPANY | N emails (mock) |
| A2.8 | Idempotencia bulk | re-ejecutar mismo request | no duplicar (si idempotency_key) |
| A2.9 | Transacción parcial | falla email empresa 2 | voucher 2 creado; email best-effort |
| A2.10 | 100+ empresas | performance smoke | completa < umbral / sin N+1 grave |

---

## B. Validación (sin mutar estado)

### B.1 — `ValidateVoucherUseCase`

| ID | Escenario | Esperado |
|----|-----------|----------|
| B1.1 | Serial existente ACTIVE en vigencia | preview OK |
| B1.2 | Serial inexistente | `PROMO_001` |
| B1.3 | Serial case-insensitive | `wlgx-gft-abc` = `WLGX-GFT-ABC` |
| B1.4 | REDEEMED | `PROMO_002` |
| B1.5 | EXPIRED | `PROMO_002` |
| B1.6 | REVOKED | `PROMO_002` |
| B1.7 | ACTIVE fuera de vigencia (before) | `PROMO_004` |
| B1.8 | ACTIVE fuera de vigencia (after) | `PROMO_004` |
| B1.9 | COMPANY scope — empresa correcta | preview OK |
| B1.10 | COMPANY scope — empresa distinta | `PROMO_005` |
| B1.11 | OPEN scope — cualquier empresa | preview OK |
| B1.12 | FIRST_TAKE no redimido | preview OK |
| B1.13 | FIRST_TAKE ya redimido | `PROMO_006` |
| B1.14 | Plan elegido en lista | preview con descuento correcto |
| B1.15 | Plan no en lista | `PROMO_003` |
| B1.16 | Sin plan en input (multi-plan) | preview lista planes elegibles |
| B1.17 | GIFT — monto final $0 | `final_amount=0` |
| B1.18 | DISCOUNT 20% sobre 100 | `final_amount=80` |
| B1.19 | DISCOUNT 100% | `final_amount=0` |
| B1.20 | Context ONBOARDING sin company | permitido si OPEN/FIRST_TAKE |
| B1.21 | Context SETTINGS sin subscription_id | planes del bono listados |
| B1.22 | Empresa con plan actual inferior a gift Pro | preview OK upgrade |
| B1.23 | Empresa con plan Enterprise, gift Basic | `PROMO_003` |
| B1.24 | Empresa con plan Pro, gift Pro | preview extensión meses |
| B1.25 | Empresa con beneficio activo | `PROMO_011` |

---

## C. Redención — Bono regalo (`GIFT`)

### C.1 — Onboarding

| ID | Escenario | Esperado |
|----|-----------|----------|
| C1.1 | Gift Pro, usuario elige Pro, OPEN | monto $0, **paso payment obligatorio** (tarjeta) |
| C1.2 | Gift Pro, usuario elige Basic | `PROMO_003` |
| C1.3 | Finalize con gift aplicado | CompanySubscription Pro, price_paid=0 |
| C1.4 | PromotionBenefit creado | benefit_end = now + 3 meses |
| C1.5 | Voucher → REDEEMED | estado correcto |
| C1.6 | Redemption context=ONBOARDING | registro auditoría |
| C1.7 | Re-finalize mismo onboarding | idempotente |
| C1.8 | Gift $0 + payment step | tarjeta capturada, PaymentMethod creado en finalize |
| C1.9 | Charge finalize gift $0 | charge monto 0 o skip charge con PM guardado (política documentada) |

### C.2 — Settings — mismo plan

| ID | Escenario | Esperado |
|----|-----------|----------|
| C2.1 | Empresa Pro, gift Pro 3 meses | benefit activo 3 meses |
| C2.2 | Próxima renovación dentro beneficio | sin cobro |
| C2.3 | Renovación después benefit_end | cobro normal Pro |
| C2.4 | benefit_months=1 | un solo ciclo sin cobro |

### C.3 — Settings — upgrade temporal (plan superior)

| ID | Escenario | Esperado |
|----|-----------|----------|
| C3.1 | Empresa Basic, gift Enterprise 2 meses | upgrade inmediato Enterprise |
| C3.2 | previous_subscription guardado | Basic en PromotionBenefit |
| C3.3 | Al benefit_end | revert a Basic (job) |
| C3.4 | pending_subscription coherente | sin conflicto downgrade manual |
| C3.5 | Usuario cancela durante beneficio | política: beneficio continúa o cancela (documentar) |
| C3.6 | Segundo gift durante beneficio activo | `PROMO_011` |
| C3.7 | Redimir tras benefit_end | OK si no hay otro beneficio activo |

### C.4 — Settings — plan inferior (rechazo)

| ID | Escenario | Esperado |
|----|-----------|----------|
| C4.1 | Empresa Pro, gift Basic | `PROMO_003` |
| C4.2 | Empresa Enterprise, gift Pro | `PROMO_003` |

### C.5 — Alcance

| ID | Escenario | Esperado |
|----|-----------|----------|
| C5.1 | COMPANY company_a, redime company_a | OK |
| C5.2 | COMPANY company_a, redime company_b | `PROMO_005` |
| C5.3 | OPEN, redime company_a | OK |
| C5.4 | OPEN, redime company_b otro serial mismo voucher | N/A un serial |
| C5.5 | FIRST_TAKE, company_a primero | OK, REDEEMED |
| C5.6 | FIRST_TAKE, company_b después | `PROMO_006` |

---

## D. Redención — Bono descuento (`DISCOUNT`)

### D.1 — Onboarding

| ID | Escenario | Esperado |
|----|-----------|----------|
| D1.1 | 20% Pro, elige Pro precio 100 | pago 80 |
| D1.2 | 50% [Basic, Pro], elige Basic 50 | pago 25 |
| D1.3 | Plan no en lista | `PROMO_003` |
| D1.4 | 100% descuento | $0 cobro, **payment step obligatorio** |
| D1.5 | duration_months=3 | PromotionBenefit 3 ciclos descuento |

### D.2 — Settings — upgrade con descuento

| ID | Escenario | Esperado |
|----|-----------|----------|
| D2.1 | 30% upgrade a Pro | cargo upgrade con 30% off |
| D2.2 | Plan destino no en lista | `PROMO_003` |
| D2.3 | Plan inferior | `PROMO_003` |
| D2.4 | Empresa con beneficio discount activo | `PROMO_011` al intentar otro bono |

### D.3 — Settings — renovación con descuento

| ID | Escenario | Esperado |
|----|-----------|----------|
| D3.1 | Descuento en plan actual | próxima renovación con % |
| D3.2 | remaining_discount_cycles decrementa | 3→2→1→0 |
| D3.3 | Ciclos agotados | cobro pleno |
| D3.4 | Descuento expira mid-cycle | política prorrateo (documentar; default ciclo completo) |

### D.4 — Cálculo de precios (`pricing.py`)

| ID | Entrada | Esperado |
|----|---------|----------|
| D4.1 | price=100, 20% | 80 |
| D4.2 | price=99, 33% | redondeo bancario definido |
| D4.3 | price=0 | 0 |
| D4.4 | percent=100 | 0 |
| D4.5 | percent decimal 33.33 | regla de redondeo |

---

## E. Ciclo de vida y expiración

| ID | Escenario | Esperado |
|----|-----------|----------|
| E1 | ACTIVE → job expiry → EXPIRED | status actualizado |
| E2 | REDEEMED no cambia con job | sigue REDEEMED |
| E3 | REVOKED no cambia con job | sigue REVOKED |
| E4 | Revoke ACTIVE | REVOKED |
| E5 | Revoke REDEEMED | error / `PROMO_007` |
| E6 | Revoke EXPIRED | error |
| E7 | Redimir EXPIRED | `PROMO_002` |
| E8 | Redimir REVOKED | `PROMO_002` |
| E9 | Vigencia empieza mañana | hoy `PROMO_004` |
| E10 | Vigencia termina hoy 23:59 | hoy OK (timezone tenant/platform) |

---

## F. Idempotencia y concurrencia

| ID | Escenario | Esperado |
|----|-----------|----------|
| F1 | Doble POST redeem mismo idempotency_key | misma respuesta, 1 redemption |
| F2 | Doble POST redeem sin key | segundo `PROMO_006` o `PROMO_008` |
| F3 | FIRST_TAKE race dos empresas | solo una gana (select_for_update) |
| F4 | Validate + redeem paralelo mismo serial | uno gana, otro error |
| F5 | Onboarding apply dos seriales distintos | segundo rechazado |
| F6 | Redimir con beneficio activo | `PROMO_011` |

---

## G. Integración billing

| ID | Escenario | Esperado |
|----|-----------|----------|
| G1 | Charge con redemption metadata | invoice con descuento |
| G2 | Charge $0 gift | charge monto 0; PaymentMethod persistido; factura con anexo bono |
| G10 | Invoice con bono | PDF/contexto incluye anexo: serial, tipo, original, descuento, total |
| G3 | renew_subscription gift activo | skip charge |
| G4 | renew_subscription discount activo | monto reducido |
| G5 | renew después beneficio | charge pleno |
| G6 | revert_gift_subscription job | plan anterior restaurado |
| G7 | Upgrade + charge con descuento | invoice línea descuento |
| G8 | Failed charge no redime | voucher sigue ACTIVE si redeem atómico post-cobro |
| G9 | Redeem atómico: cobro falla | rollback redemption (transacción) |

---

## H. Emails

| ID | Escenario | Esperado |
|----|-----------|----------|
| H1 | Create COMPANY gift | `GIFT_VOUCHER` enviado |
| H2 | Create COMPANY discount | `DISCOUNT_VOUCHER` enviado |
| H3 | Create OPEN | sin email empresa |
| H4 | Email service down | voucher creado igual |
| H5 | Contexto template completo | serial, plan, fechas en body |
| H6 | Bulk 3 empresas | 3 envíos |

---

## I. API — Admin

| ID | Escenario | Esperado |
|----|-----------|----------|
| I1 | GET list sin auth | 401 |
| I2 | GET list admin | 200 paginado |
| I3 | Filtro por status ACTIVE | solo activos |
| I4 | Filtro por voucher_type | GIFT only |
| I5 | Filtro por company_id | |
| I6 | POST create válido | 201 + data |
| I7 | POST bulk | 201 + resumen |
| I8 | POST revoke | 200 |
| I9 | Usuario tenant en admin API | 403 |
| I10 | wrap_response envelope | status_code, data |

---

## J. API — Tenant / Onboarding

| ID | Escenario | Esperado |
|----|-----------|----------|
| J1 | POST validate tenant autenticado | 200 preview |
| J2 | POST redeem tenant | 200 + benefit |
| J3 | POST redeem otra empresa | 403/405 |
| J4 | POST onboarding validate sin cookie | 401 |
| J5 | POST onboarding apply + state | serial en state |
| J6 | Onboarding apply expirado | 400 PROMO_* |
| J7 | Member sin permiso billing | según permiso definido |

---

## K. Seguridad y abuso

| ID | Escenario | Esperado |
|----|-----------|----------|
| K1 | Fuerza bruta serial | rate limit (si implementado) |
| K2 | Serial en logs | enmascarado parcial |
| K3 | Metadata compra con XSS | escapado en emails |
| K4 | Tenant A no lista vouchers de tenant B | aislamiento admin solo platform |

---

## L. Regresión onboarding (sin bono)

| ID | Escenario | Esperado |
|----|-----------|----------|
| L1 | Registro plan pago sin bono | flujo actual intacto |
| L2 | Registro plan gratis sin bono | skip payment (sin cambio — plan price=0) |
| L3 | Finalize sin voucher en state | sin PromotionRedemption |

---

## M. Compra pública (Fase 5)

| ID | Escenario | Esperado |
|----|-----------|----------|
| M1 | Preview catálogo gift Pro 3m | precio catálogo |
| M2 | Preview catálogo discount Pro 20% 3 renov. | precio catálogo |
| M3 | Checkout gift pago OK | voucher GIFT OPEN creado |
| M4 | Checkout discount pago OK | voucher DISCOUNT OPEN creado |
| M5 | Checkout pago falla | sin voucher |
| M6 | Email destinatario gift | `GIFT_VOUCHER_PURCHASE` |
| M7 | Email destinatario discount | `DISCOUNT_VOUCHER_PURCHASE` |
| M8 | Email comprador | `VOUCHER_PURCHASE_CONFIRM` |
| M9 | PaymentMethod no persistido | sin fila en payment_methods |
| M10 | Respuesta incluye serial | pantalla final |
| M11 | Reintento checkout idempotente | 1 voucher |

---

## N. Matriz combinada tipo × alcance × contexto

Caso mínimo obligatorio (smoke de integración):

| Tipo | Alcance | Contexto | Resultado |
|------|---------|----------|-----------|
| GIFT | COMPANY | — (solo create) | email + ACTIVE |
| GIFT | OPEN | ONBOARDING | $0 + REDEEMED |
| GIFT | OPEN | SETTINGS mismo plan | benefit N meses |
| GIFT | OPEN | SETTINGS upgrade | temporal + revert |
| GIFT | FIRST_TAKE | SETTINGS | primera OK, segunda falla |
| DISCOUNT | COMPANY | — | email |
| DISCOUNT | OPEN | ONBOARDING | precio reducido |
| DISCOUNT | OPEN | SETTINGS upgrade | cargo reducido |
| DISCOUNT | OPEN | SETTINGS renovación | ciclos descuento |
| DISCOUNT | FIRST_TAKE | ONBOARDING | primera OK |
| DISCOUNT | OPEN | PUBLIC_PURCHASE | voucher OPEN creado |

---

## O. Tests E2E (base-client-web — Fase 4, opcional en CI)

| ID | Flujo | Pasos | Esperado |
|----|-------|-------|----------|
| O1 | Onboarding gift | start → … → aplicar serial → payment (tarjeta) → done | tenant creado, PM guardado |
| O2 | Onboarding discount | serial 20% → pago muestra 80% | |
| O3 | Settings redeem gift | login → settings → redimir → confirm | beneficio visible |
| O4 | Settings redeem inválido | serial falso | mensaje error i18n |
| O5 | Serial expirado | | toast error PROMO_004 |
| O6 | Settings beneficio activo | intentar otro serial | error PROMO_011 | E2E O6 |

Documentar en `e2e/tests/promotions.spec.ts` (crear en Fase 4).

---

## M-client. Tests E2E compra pública (base-client-web — Fase 5)

| ID | Flujo | Pasos | Esperado |
|----|-------|-------|----------|
| M1 | Happy path gift | wizard → pago OK | success + serial |
| M2 | Preview plan inválido | elegir plan FREE | error preview |
| M3 | Pago rechazado | tarjeta decline | sin redirect success |
| M4 | Idempotencia | mismo `idempotency_key` ×2 | mismo serial, 1 voucher |

Documentar en `e2e/tests/public-purchase.spec.ts`. Mocks en `e2e/fixtures/api-mocks.ts`
(`promotions/public/purchase/preview|checkout`).

---

## Actividades

- [x] Implementar `conftest.py` con factories reutilizables.
- [x] Cubrir tablas A–N con tests en verde.
- [x] Añadir `test_evaluation_matrix.py` que parametrice filas críticas de B, C, D, E.
- [x] Integration tests con BD real (`pytest -m integration`).
- [x] API tests con `APIClient` y usuarios admin/tenant.
- [x] Documentar comando: `pytest platform/tests/unit/billing/promotion/ platform/tests/integration/billing/promotion/ -m "unit or integration"`.
- [ ] Cobertura mínima acordada: **≥90%** en `application/` y `pricing.py`.
- [x] Tests M marcados `@pytest.mark.skip` hasta Fase 5.
- [x] Tests O en base-client-web Fase 4 (`e2e/tests/promotions.spec.ts`, O1–O8).
- [x] Tests M-client en base-client-web Fase 5 (`e2e/tests/public-purchase.spec.ts`, M1–M4).

### Comando de ejecución

```bash
# Unit + API (sin Postgres)
pytest platform/tests/unit/billing/promotion/ platform/tests/api/billing/promotion/ client/tests/unit/onboarding/test_onboarding_promotion_step.py -m "unit or api"

# Integración (requiere Postgres + migrate_schemas)
pytest platform/tests/integration/billing/promotion/ client/tests/integration/onboarding/test_finalize_with_voucher.py -m integration
```

---

## Definición de Done — Fase 2

- [x] Todas las filas A1–L3 tienen test automatizado en verde.
- [x] Matriz N (10 combinaciones) pasa en integration.
- [ ] Tests de concurrencia F3 pasan (o skip documentado si SQLite).
- [x] `pytest -m unit` promociones < 60s en CI.
- [x] Ningún test depende de base-admin-web ni base-client-web.
- [x] README/comando documentado en resumen teórico.

### Archivos añadidos (referencia)

| Archivo | Rol |
|---------|-----|
| `platform/tests/unit/billing/promotion/test_evaluation_matrix.py` | Matriz parametrizada |
| `platform/tests/integration/billing/promotion/test_gift_upgrade_revert.py` | Reversión plan superior |
| `platform/tests/api/billing/promotion/test_admin_voucher_api.py` | Contrato HTTP admin |
