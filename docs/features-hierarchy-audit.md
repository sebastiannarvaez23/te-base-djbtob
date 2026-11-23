# Auditoría de jerarquía de features — base

Estándar de construcción de monolitos (4 niveles) y estado post-remediación
(oleadas 0–6, 2026-09-18).

- Estándar en producto: `README.md` § Jerarquía de features (4 niveles)
- Regla Cursor: `.cursor/rules/monolith-feature-hierarchy.mdc`
- Plan: [`features-hierarchy-remediation-plan.md`](./features-hierarchy-remediation-plan.md)
- Inventario: [`features-distribution-tree.md`](./features-distribution-tree.md)
- Guardrail CI: `core/tests/unit/test_feature_hierarchy_convention.py`

---

## Estándar (obligatorio)

| Nivel | Nombre | Qué representa | ¿Clean Architecture? | Ejemplo |
|------:|--------|----------------|----------------------|---------|
| **1** | Mundo | Fuente de información / bounded context de despliegue | No | `client`, `platform`, `handbook` |
| **2** | Feature | Conjunto de lógicas **desacoplado**, candidato a MS | **No** | `client/features/warehouse` |
| **3** | Lógica conjunta | Familia / subdominio | **No** | `warehouse/inventory` |
| **4** | Entidad | Lógica específica de una entidad | **Sí** | `warehouse/inventory/balances` |

Forma canónica:
`{mundo}/features/{L2}/{L3}/{L4}/{domain,application,infrastructure,presentation}/`

---

## Veredicto post-remediación

| Mundo | Estado | Notas |
|-------|--------|-------|
| client | **OK** | Críticos y L3 resueltos; `warehouse/foundation` es helper plano (sin carpetas CA) |
| platform | **OK** | Familias L3 + wrappers 1:1 aplicados |
| handbook | **OK** | Un solo L2 `docs` → `content` / `governance` |

**CA en raíz L2:** ninguna (guardrail unitario).

---

## Forma actual (resumen)

```text
client/features/
  warehouse/{inventory,inbound,fulfillment,site,ops}/… + foundation helper (plano)
  logging/{audit_trail,security,ops,system}/… + facade
  security/{access,identity,lifecycle}/…
  communication/{assistant/chat, messaging/inbox}
  integrations/{connections/profile, oauth/client} + facade
  partners/third_parties/party

platform/features/
  billing/{subscription,commerce,quota}/… + common
  security/{access,identity,auth}/…
  configuration/{parameters,landing,assistant}/…
  communication/{email,messaging}/… + notification
  company/tenant/… · support/{incidents,ops}/…
  compliance|documents|geography|integrations|release → L3 1:1

handbook/features/
  docs/{content,governance}/…
```

---

## Historial

La matriz detallada de hallazgos **antes** de remediación quedó supersedida por las
oleadas 1–6 del plan. Conservar este archivo como baseline de cumplimiento y
referencia del estándar.
