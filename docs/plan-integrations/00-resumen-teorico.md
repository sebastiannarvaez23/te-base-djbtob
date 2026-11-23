# Plan de Trabajo Integraciones — Resumen teórico (base)

> **Propósito de este documento.** Es la hoja de ruta única y compartida para
> incorporar **integrabilidad con ERPs, proveedores y aplicaciones externas del
> cliente** en la plataforma WMS de forma limpia, escalable y mantenible. Está
> escrito para que **cualquier colega del equipo** entienda qué se va a construir,
> por qué, en qué orden, cómo se separa de billing / parámetros / feature flags,
> y cómo encaja en la arquitectura existente.
>
> **Cómo se usa.** Este archivo contiene la parte **teórica** (contexto, glosario,
> fronteras, arquitectura, entornos, gobernanza de datos y mapa de fases). Cada
> fase de construcción vive en su propio archivo dentro de
> `docs/plan-integrations/`. Marca `[x]` cuando una actividad esté **terminada y
> verificada** (ver *Definición de Done* de cada fase).

---

## Índice

### Teoría (este archivo)

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Glosario](#2-glosario)
3. [Fronteras con capas existentes](#3-fronteras-con-capas-existentes)
4. [Principios de arquitectura](#4-principios-de-arquitectura)
5. [Tipos de integración](#5-tipos-de-integración)
6. [Modelo de entornos (prosandbox → cliente)](#6-modelo-de-entornos-prosandbox--cliente)
7. [Fuente de verdad, sync e idempotencia](#7-fuente-de-verdad-sync-e-idempotencia)
8. [Secretos, PII y cumplimiento global](#8-secretos-pii-y-cumplimiento-global)
9. [Observabilidad y resiliencia](#9-observabilidad-y-resiliencia)
10. [Acoplamiento con otros planes](#10-acoplamiento-con-otros-planes)
11. [Mapa de fases (resumen)](#11-mapa-de-fases-resumen)
12. [Bitácora de decisiones](#12-bitácora-de-decisiones)

### Fases de construcción (un archivo cada una)

- [FASE 1 — Capa transversal (`core/integrations/`)](fase-1-capa-transversal.md)
- [FASE 2 — Capa multitenant y MVP Pedidos (SAP / SIESA)](fase-2-multitenant.md)
- [FASE 3 — Suite de tests unitarios](fase-3-tests.md)
- [FASE 4 — Administración plataforma (`base-admin-web`)](fase-4-admin-web.md)
- [FASE 5 — Autogestión IT del cliente (`base-client-web`)](fase-5-client-web.md)
- [FASE 6 — ProSandbox interno (`wa-prosandbox-web` + `base-prosandbox`)](fase-6-prosandbox.md)

---

## 1. Contexto y objetivo

**base** es el backend de un WMS SaaS multi-tenant (django-tenants, un
schema PostgreSQL por empresa). la base abstrae procesos logísticos y debe
integrarse con el ecosistema del cliente: **ERPs** (SAP, SIESA), **proveedores**
(pagos, transporte, etc.) y **aplicaciones propias** del cliente (inventarios
paralelos, e-commerce, CRM).

**Objetivo de este plan:** construir una base transversal de integraciones que
permita:

- Conectar **varias integraciones por tenant** (ej. ERP + app de inventarios).
- Ofrecer **conectores ERP especializados** (producto de la base, versionado
  internamente) y **conectores de aplicación** evolutivos (el cliente conecta
  sus sistemas **hacia** la base).
- Operar en **batch** inicialmente, con visión híbrida futura (eventos +
  batch).
- Mantener al **WMS como fuente de verdad** de la información logística.
- Ser **configurable por el admin IT del cliente**, con gobierno y soporte desde
  plataforma (`base-admin-web`).
- Ser **resiliente, idempotente y monitorizable** desde el día uno.
- Respetar **entitlements** (`core/access`) y el catálogo de features
  (`integrations.*`) — cada integración activable por plan/rol.

**MVP acordado:** módulo de **Pedidos** (`orders`), conectores **SAP** y
**SIESA**, sincronización **batch**.

**No-objetivos (lo que este plan NO hace en la primera entrega):**

- No reemplaza `platform/features/billing/payments/` (cobro de suscripción SaaS).
- Los proveedores de pago del **cliente** usan el mismo framework de conectores,
  pero no se mezclan con el billing de plataforma.
- No implementa iPaaS visual completo ni SDK de plugins del cliente en Fase 1–2.
- `wa-prosandbox-*` **nunca** se despliega en producción (solo desarrollo
  interno de la base).
- No bloquea el arranque del WMS si un conector externo está caído.

---

## 2. Glosario

| Concepto | Qué es | Dónde vive |
|----------|--------|------------|
| **Conector (connector)** | Adaptador que traduce entre un sistema externo y contratos internos de la base | `core/integrations/connectors/` |
| **Catálogo de conector** | Definición global del tipo SAP, SIESA, webhook-inbound, etc. | `platform/…/connector_catalog/` (schema `public`) |
| **Conexión (connection)** | Instancia configurada por un tenant (URL, credenciales, entorno) | `client/features/integrations/connection/` |
| **Mapeo (mapping)** | Reglas campo-a-campo entre payload externo y DTO interno | `client/features/integrations/mapping/` |
| **Sync run** | Ejecución batch de sincronización (pedidos, etc.) | `client/features/integrations/sync/` |
| **Outbox** | Eventos internos pendientes de enviar al externo | `client/features/integrations/sync/outbox/` |
| **Inbox** | Eventos/webhooks recibidos del externo pendientes de procesar | `client/features/integrations/sync/inbox/` |
| **Integration log** | Traza HTTP/request de integración (ya existe parcialmente) | `client/features/logging/integration/` |
| **Entitlement** | ¿El plan permite `integrations.order-sync`? | `core/access` |
| **Release flag** | ¿Ejecuto implementación nueva del sync? | `core/flags` (opcional por conector) |

---

## 3. Fronteras con capas existentes

Orden de evaluación en un request o job de sync:

```
1. Autenticación / tenant context
2. core/access     → ¿el plan incluye integrations.order-sync (u otra)?
3. Rol / permiso   → ¿el usuario IT puede administrar conexiones?
4. Conexión activa → ¿la instancia está habilitada y en el entorno correcto?
5. core/integrations → ejecutar conector con idempotencia + logging
6. Use case de dominio (orders, inventories, …) → WMS como fuente de verdad
```

| Capa existente | Relación con integraciones |
|----------------|---------------------------|
| `core/ai/` | Fase posterior: mapeo asistido ([plan-ia fase 6](../plan-ia/fase-6-integraciones-ia.md)) |
| `core/flags/` | Rollout gradual de conectores nuevos (`integrations.sap.orders_v2`) |
| `core/parameters` | Solo defaults globales de plataforma (timeouts, límites); **no** credenciales tenant |
| `platform/billing/payments` | Billing SaaS; patrón de referencia (`IPaymentGateway`), no reutilización directa |
| `client/logging/integration` | Destino de trazas; se enriquece, no se duplica |
| `core/tasks` (`TenantTask`) | Ejecución batch por schema |
| `automation` (futuro) | Triggers/acciones consumirán eventos de `integrations` vía facade |

---

## 4. Principios de arquitectura

### 4.1 Gemelo de `core/ai/` y `core/storage/`

El dominio define **puertos**; la infraestructura provee **adaptadores**
intercambiables. Los use cases de negocio (orders, inventories) dependen de
facades (`push_order`, `pull_orders`), nunca de SAP/SIESA directamente.

### 4.2 Dos mundos Django (como el resto del proyecto)

| Mundo | Responsabilidad |
|-------|-----------------|
| **`core/integrations/`** | Contratos, runner, resiliencia, registry de clases de conector, secret store abstracto |
| **`platform/features/integrations/`** | Catálogo global, límites por plan, monitoreo cross-tenant, soporte |
| **`client/features/integrations/`** | Conexiones, mapeos, sync runs, webhooks inbound, API IT del tenant |
| **`client/features/warehouse/orders/`** | Dominio Pedidos; expone hooks/eventos que integraciones consume |

### 4.3 Hexagonal estricto

ViewSets → use case → repositorio. El conector se inyecta vía factory
(`get_connector(connection_id)`). Ningún ViewSet importa SDK de SAP.

### 4.4 la base provee conectores; el cliente conecta hacia nosotros

- **ERP (SAP, SIESA):** la base implementa adaptadores salientes (pull/push
  batch) hacia APIs del cliente.
- **Aplicaciones del cliente:** la base expone **API REST documentada** +
  **webhooks inbound** autenticados; el equipo del cliente implementa su lado.
  Los conectores "app" evolucionan según demanda (no bloquean el MVP).

---

## 5. Tipos de integración

```
┌─────────────────────────────────────────────────────────────────┐
│                    core/integrations/                           │
│  IConnector · ISyncOrchestrator · ISecretStore · IIdempotency   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌───────────┐      ┌─────────────┐     ┌──────────────┐
  │ ERP       │      │ Proveedor   │     │ App cliente  │
  │ SAP       │      │ pagos       │     │ webhook-in   │
  │ SIESA     │      │ transporte  │     │ REST out     │
  └───────────┘      └─────────────┘     └──────────────┘
```

| Tipo | Implementación | MVP |
|------|----------------|-----|
| **ERP** | Conector especializado por proveedor | SAP + SIESA (Pedidos) |
| **Proveedor** | Mismo framework; adaptador por proveedor | Estructura lista; implementación cuando haya demanda |
| **App cliente** | Inbound webhook + base API | Contrato base en Fase 2; UI en Fase 5 |

---

## 6. Modelo de entornos (prosandbox → cliente)

Cada **conexión** declara su `environment`:

| Valor | Uso |
|-------|-----|
| `PROSANDBOX` | Apunta a `base-prosandbox` (solo dev interno de la base) |
| `CLIENT_TEST` | Entorno de pruebas del cliente (UAT) |
| `CLIENT_PROD` | Producción del cliente |

Reglas:

- Una conexión **no** puede promoverse automáticamente; el admin IT copia
  configuración y valida con **test connection** + **dry-run**.
- Credenciales son **por entorno** (nunca compartidas entre PROD y TEST).
- `PROSANDBOX` solo es seleccionable en despliegues no productivos de la base.

---

## 7. Fuente de verdad, sync e idempotencia

### 7.1 WMS como fuente de verdad

| Dirección | Comportamiento |
|-----------|----------------|
| **Inbound** (externo → WMS) | Crea/actualiza pedidos solo vía reglas de sync; conflictos resueltos a favor del WMS |
| **Outbound** (WMS → externo) | Propaga estado autoritativo del WMS; reintentos idempotentes |

El `ConflictResolver` (Fase 1) implementa política **WMS_WINS**: si el externo
discrepa, se registra la divergencia, se mantiene el estado WMS y se notifica
(opcionalmente outbox de reconciliación manual).

### 7.2 Visión híbrida (batch ahora, eventos después)

**Fase 2 (batch):** Celery `TenantTask` + schedule por conexión.

**Futuro:** outbox interno → worker envía; inbox para webhooks. La estructura
de tablas `sync_outbox` / `sync_inbox` se crea en Fase 2 vacía o mínima para
no reescribir después.

### 7.3 Idempotencia

- Clave: `{connection_id}:{entity}:{external_id}:{operation}:{payload_hash}`.
- Store en Redis (TTL) + registro en BD para auditoría.
- Reintentos de Celery no duplican pedidos.

---

## 8. Secretos, PII y cumplimiento global

### 8.1 Secretos (decisión recomendada)

**Fase 1–2: cifrado en reposo con clave maestra de plataforma**

```
INTEGRATIONS_SECRET_KEY  →  env / KMS (producción)
TenantSecret (BD)        →  ciphertext AES-GCM por tenant+connection
API nunca devuelve       →  secretos en claro (solo máscara ····1234)
```

Motivos: estándar en SaaS multi-tenant (Stripe, Shopify Partners), sin
infraestructura extra en MVP, compatible con migración futura a **AWS Secrets
Manager** o **HashiCorp Vault** por tenant enterprise.

**Reglas:**

- Rotación: el admin IT puede rotar credenciales sin borrar la conexión.
- Logs: `core/logging_redaction.py` enmascara tokens antes de persistir.
- Acceso: solo roles IT + soporte de la base (auditoría en `core/audit`).

### 8.2 PII y residencia de datos

- Los payloads de sync se **minimizan**: solo campos necesarios al mapeo de
  pedidos (referencia, líneas, cantidades — no datos innecesarios del ERP).
- Retención de `IntegrationLog` alineada a `client/features/logging/retention`.
- Datos de un tenant **nunca** cruzan schema; jobs usan `TenantTask`.
- Para clientes con requisitos GDPR: export/borrado vía procesos de tenant
  existentes; integraciones no almacenan copia redundante del ERP más allá del
  sync run y logs acotados.

---

## 9. Observabilidad y resiliencia

### 9.1 Indispensable (Fase 1–2)

| Capacidad | Implementación |
|-----------|----------------|
| Integration log | Facade → `client/logging/integration` |
| Sync run record | Estado, duración, conteos, error |
| Idempotencia | Redis + BD |
| Reintentos | `BaseTask` + backoff en jobs batch |
| Test connection | Ping al endpoint del conector |
| Dry-run | Ejecuta mapeo sin persistir en WMS |
| Circuit breaker lite | N fallos consecutivos → pausa conexión + alerta |

### 9.2 Evolutivo

- Dashboard de salud por conexión (Fase 4–5).
- DLQ explícita y replay manual.
- Métricas Prometheus / OpenTelemetry.
- Alertas proactivas (email/inbox).

---

## 10. Acoplamiento con otros planes

| Plan | Acoplamiento |
|------|--------------|
| [plan-ia fase 6](../plan-ia/fase-6-integraciones-ia.md) | Mapeo asistido consume `mapping` del tenant; requiere Fase 1–2 |
| [plan-feature-flags](../plan-feature-flags/00-resumen-teorico.md) | Rollout de conectores nuevos |
| [plan-ia fase 4](../plan-ia/fase-4-instrumentacion-datos.md) | Eventos de sync alimentan ML futuro |
| Módulo `orders` (por construir) | Publica eventos de dominio; integraciones los consume |
| Módulo `automation` (futuro) | `event-triggers` escuchan `integration.sync_completed` |
| `feature_registry.py` | `integrations.order-sync` gate del MVP |

**Orden de ejecución paralela sugerido:**

1. Fase 1 integraciones (tubería) **en paralelo** con diseño del módulo orders.
2. Fase 2 integraciones cuando orders tenga contrato mínimo de creación/estado.
3. Fases 4–5 UI cuando API tenant esté estable.
4. Fase 6 prosandbox cuando SAP/SIESA tengan contrato HTTP definido.
5. plan-ia fase 6 después de mapping estable en Fase 2.

---

## 11. Mapa de fases (resumen)

| Fase | Entregable principal | Repo(s) |
|------|---------------------|---------|
| **1** | `core/integrations/` — puertos, runner, fake connector, secret store | base |
| **2** | Catálogo platform + conexiones tenant + sync batch Pedidos SAP/SIESA | base |
| **3** | Tests unitarios matriz completa | base |
| **4** | UI admin: catálogo, límites, monitoreo, soporte | base-admin-web |
| **5** | UI cliente IT: conexiones, mapeos, test, dry-run, historial | base-client-web |
| **6** | Simuladores SAP/SIESA para dev interno | wa-prosandbox-* |

---

## 12. Bitácora de decisiones

| Fecha | Decisión |
|-------|----------|
| 2026-07-06 | MVP = Pedidos + SAP + SIESA + batch |
| 2026-07-06 | WMS fuente de verdad; política WMS_WINS |
| 2026-07-06 | Múltiples conexiones por tenant |
| 2026-07-06 | Secretos: cifrado en BD + clave maestra env/KMS; migración Vault opcional |
| 2026-07-06 | la base implementa conectores ERP; apps del cliente conectan hacia la base |
| 2026-07-06 | ProSandbox solo desarrollo interno, nunca producción |
| 2026-07-06 | Entitlements `integrations.*` desde el inicio |
| 2026-07-06 | Fases 1–3 completadas en base (47 tests unitarios integraciones) |
| 2026-07-06 | Fases 4–6 (UI admin/cliente, ProSandbox) diferidas para desarrollo posterior |
