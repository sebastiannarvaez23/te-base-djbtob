# Plan de remediación — jerarquía L1–L4

Plan operativo para alinear `base` al estándar de 4 niveles
(documentado en `README.md` y auditado en `features-hierarchy-audit.md`).

**Objetivo:** CA solo en L4; L2 = frontera de microservicio sin CA; L3 = familia
sin CA.

**Fuera de alcance de este plan:** reescritura funcional, cambios de API
pública salvo que un move de paquete lo exija, cableado nuevo de permisos.

---

## Principios de ejecución

1. **Una oleada = un PR** (o un PR por L2 si el diff explota).
2. Primero **mover paquetes + imports + `INSTALLED_APPS` / labels**; luego
   ajustar tests; migraciones solo si cambia `app_label` o tablas.
3. No mezclar remediación estructural con features nuevas en el mismo PR.
4. Tras cada oleada: `pytest -m unit` del área tocada + smoke de imports.
5. Congelar el estándar **antes** de mover código (README + rule Cursor) —
   ya hecho al iniciar este plan.

### Done de cada move

- [ ] L2 sin `domain/` / `application/` / `infrastructure/` / `presentation/`
- [ ] L3 (si aplica) sin esas carpetas
- [ ] L4 con las cuatro capas CA (o justificación documentada si es kernel
      incompleto a propósito, p. ej. foundation → helper)
- [ ] Apps Django / URLs / tests actualizados
- [ ] Sin regresiones unitarias del módulo

---

## Oleada 0 — Gobernanza (hecha / check)

| Ítem | Estado |
|------|--------|
| Documentar 4 niveles en `README.md` | Hecho con este plan |
| Regla Cursor `monolith-feature-hierarchy.mdc` | Hecho con este plan |
| Auditoría baseline `features-hierarchy-audit.md` | Hecho |
| Features **nuevas** solo en forma canónica | En vigor desde ya |

---

## Oleada 1 — Críticos client (CA en L2)

Prioridad máxima: rompen la frontera de extracción.

**Estado:** completada (2026-09-18). Labels Django conservados (`assistant`, `third_parties`, `integrations`).

### 1.1 `assistant` → L4 bajo L2 real ✅

**Hecho:**

```text
client/features/communication/          # L2
  assistant/                            # L3
    chat/                               # L4 + CA (+ realtime helper)
```

### 1.2 `third_parties` → L4 bajo L2 de maestros ✅

**Hecho:**

```text
client/features/partners/               # L2
  third_parties/                        # L3
    party/                              # L4 + CA
```

### 1.3 `integrations` — quitar CA del L2 ✅

**Hecho:**

```text
client/features/integrations/           # L2 sin CA
  connections/
    profile/                            # L4 + CA (antes raíz)
  oauth/
    client/                             # L4 + CA (app_label=integrations)
  facade/                               # helper
```

---

## Oleada 2 — Handbook (L2 = entidad)

**Estado:** completada (2026-09-18). Labels conservados (`handbook_catalog`, `handbook_page`, `handbook_change_request`, `handbook_ingest`).

**Hecho:**

```text
handbook/features/
  docs/                                 # L2
    content/                            # L3
      catalog/                          # L4
      page/                             # L4
    governance/                         # L3
      change_request/                   # L4
      ingest/                           # L4
```

---

## Oleada 3 — Nivelar `warehouse` (client)

**Estado:** completada (2026-09-18). D3 = **C híbrida**. Labels Django conservados.

**Hecho:**

```text
warehouse/                              # L2
  inventory/                            # L3 (ya canónico)
    balances|reference|stock            # L4
  inbound/                              # L3
    receiving|returns                   # L4
  fulfillment/                          # L3
    orders|picking|packing|dispatches   # L4
  site/                                 # L3
    facilities                          # L4
  ops/                                  # L3
    operations                          # L4
  foundation/                           # helper L2 plano (contracts + reliability; sin CA)
```

---

## Oleada 4 — Familias evidentes en platform

**Estado:** completada (2026-09-18). Labels Django conservados.

**Hecho (resumen):**

```text
billing/{subscription,commerce,quota}/…   + common helper
security/{access,identity,auth}/…
configuration/{parameters,landing,assistant}/…
communication/{email,messaging}/…         + notification helper
company/tenant/{company,users}
support/{incidents,ops}/…
compliance/policy/policy                  (L3 1:1)
documents/document_template/document_template
geography/location/location
integrations/connector_catalog/connector_catalog
release/feature_flag/feature_flag
```

---

## Oleada 5 — `logging` y `security` (client)

**Estado:** completada (2026-09-18). Labels Django conservados.

**Hecho:**

```text
logging/
  audit_trail/audit
  security/security
  ops/{operations,inventory,integration}
  system/{system,performance,errors,config,retention}
  facade/

security/
  access/{roles,features}
  identity/{identity,users}
  lifecycle/{auth,registration,onboarding}
```

---

## Oleada 6 — Cierre y calidad

**Estado:** completada (2026-09-18).

| Ítem | Resultado |
|------|-----------|
| Inventario `features-distribution-tree.md` | Actualizado a forma post-remediación |
| Auditoría `features-hierarchy-audit.md` | Reescrita como baseline de cumplimiento |
| Guardrail unitario | `core/tests/unit/test_feature_hierarchy_convention.py` — prohíbe CA en raíz L2 |
| `CLAUDE.md` | Jerarquía L1–L4 + ejemplos de path actualizados |
| Cierre deuda inbox client | `communication/messaging/inbox` (quedaba CA en slot L3) |
| Deuda `warehouse/foundation` | Helper aplanado: `contracts.py` + `reliability.py` (sin `domain/`/`infrastructure/`) |

---

## Calendario orientativo

| Oleada | Esfuerzo relativo | Dependencias |
|--------|-------------------|--------------|
| 0 Gobernanza | — | Hecha |
| 1 Críticos client | M | Ninguna |
| 2 Handbook | M | Ninguna (paralela a 1) |
| 3 Warehouse | L | Tras decisión 3.1; ideal después de 1 |
| 4 Platform familias | L | Independiente; puede ir en paralelo a 3 por equipos |
| 5 Logging / security client | M | Tras 1 |
| 6 Cierre | S | Tras 1–5 |

M ≈ 1–3 PRs · L ≈ varios PRs / varios días · S ≈ checklist + docs.

---

## Decisiones pendientes (rellenar al ejecutar)

| ID | Pregunta | Decisión | Fecha |
|----|----------|----------|-------|
| D1 | `assistant` → ¿`communication` o L2 `ai_assistant`? | **`communication`** — assistant es una lógica, no un L2; vive como L3/`chat` L4 | 2026-09-18 |
| D2 | Nombre L2 de terceros: ¿`partners` / `master_data`? | **`partners`** | 2026-09-18 |
| D3 | Warehouse: opción A / B / C | **C híbrida** — `inbound`, `fulfillment`, `site`, `ops`; `inventory` intacto; `foundation` helper L2 | 2026-09-18 |
| D4 | Handbook L2: ¿`docs` u otro nombre? | **`docs`** | 2026-09-18 |
| D5 | ¿Shim de imports durante 1 release? | **No** en oleada 1 — actualizar imports en el mismo PR | 2026-09-18 |

---

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Cambio de `app_label` → migraciones dolorosas | Preferir **mantener `label`** al mover `name`; solo cambiar path Python |
| Imports rotos en masa | Codemod / `rg` + PR por L2; shims temporales si D5 = sí |
| Confusión assistant platform vs client | Paths distintos: `platform/.../configuration/assistant` vs client L4 chat |
| Paralizar features nuevas | Oleada 0 ya obliga forma canónica en código nuevo; remediación no bloquea entregas si no tocan el área |

---

## Referencias

- Estándar: `README.md` § Jerarquía de features (4 niveles)
- Regla Cursor: `.cursor/rules/monolith-feature-hierarchy.mdc`
- Auditoría: `docs/features-hierarchy-audit.md`
- Inventario de capas: `docs/features-distribution-tree.md`
