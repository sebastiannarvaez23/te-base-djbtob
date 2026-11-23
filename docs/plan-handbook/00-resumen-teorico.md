# Plan de Trabajo Handbook — Resumen teórico (base)

> **Propósito de este documento.** Hoja de ruta única para el **manual de
> plataforma de la base**: documentación pública, del portal administrativo y del
> WMS; arquitectura, planes y visión; gobierno de cambios; almacenamiento
> PostgreSQL + MinIO; CMS; e integración con assistant y otras IAs. Está
> escrito para que cualquier colega entienda qué se construye, por qué, en qué
> orden y cómo encaja en los mundos `platform/`, `client/` y `handbook/`.
>
> **Cómo se usa.** Este archivo es la parte **teórica**. Cada fase vive en su
> propio archivo en `docs/plan-handbook/`. Marca `[x]` solo cuando la actividad
> esté **terminada y verificada**. No marques algo a medias: déjalo `[ ]` y
> anótalo en la bitácora.

---

## Índice

### Teoría (este archivo)

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Glosario](#2-glosario)
3. [Tres mundos y fronteras](#3-tres-mundos-y-fronteras)
4. [Audiencias y ACL de lectura](#4-audiencias-y-acl-de-lectura)
5. [Gobierno de cambios (solicitud + aprobación)](#5-gobierno-de-cambios-solicitud--aprobación)
6. [Almacenamiento PostgreSQL + MinIO](#6-almacenamiento-postgresql--minio)
7. [APIs para humanos e IAs](#7-apis-para-humanos-e-ias)
8. [Frontend](#8-frontend)
9. [Mapa de fases](#9-mapa-de-fases)
10. [Bitácora de decisiones](#10-bitácora-de-decisiones)

### Fases de construcción

- [FASE 0 — Cimientos (`handbook/`)](fase-0-cimientos.md)
- [FASE 1 — ACL y solicitudes de cambio (dominio)](fase-1-acl-y-solicitudes.md)
- [FASE 2 — Persistencia (PostgreSQL + MinIO)](fase-2-persistencia.md)
- [FASE 3 — APIs HTTP](fase-3-apis.md)
- [FASE 4 — Frontend `base-docs-web` (lector + CMS)](fase-4-frontend.md)
- [FASE 5 — IA (retrieve + assistant)](fase-5-ia.md)

---

## 1. Contexto y objetivo

Hoy no hay un producto de manuales. El landing apunta a `/admin/docs` (en
construcción). Las toolbars `help` / `manual` no tienen destino. El markdown de
`docs/` es ingeniería, no un CMS. assistant no tiene RAG: solo tools de
pedidos/referencias y `ui_context`.

**Objetivo:** un bounded context `handbook/` (schema `public`) que:

- Publique **manuales** (WMS, portal admin, contenido público), más
  **arquitectura**, **técnica**, **planes** y **visión**.
- Filtre cada sección por **audiencia** y por la **misma `feature_key`** que ya
  entra en sesión al login (rol ∩ suscripción en cliente; rol admin en
  plataforma).
- Impida que un cambio llegue al lector sin **aprobación** del Administrador de
  Plataforma.
- Sirva el mismo corpus a humanos y a IAs, con la **misma ACL**.
- Guarde el `.md` versionado en MinIO y el catálogo/ACL/solicitudes en
  PostgreSQL (`IStorageService` ya existe).

**No-objetivos:**

- No es `platform.features.documents` (plantillas HTML/PDF de operación).
- No sustituye `wa-help-modal` (ayuda contextual de un flujo).
- No siembra catálogo ni artículos en migraciones.
- No mezcla hechos de un tenant en el índice de documentación (el corpus es de
  plataforma; el aislamiento es por ACL del lector).
- No usa el Administrator **de la empresa cliente** para editar el manual.

---

## 2. Glosario

| Término | Qué es |
|---------|--------|
| **Lector** | Anónimo, usuario cliente o admin de plataforma que **consulta** contenido publicado. |
| **Admin tecnológico** | Usuario de **plataforma** (`AdminUser`) con `admin.docs.propose`. Redacta y envía solicitudes. **No** es el Administrator del tenant. |
| **Administrador de Plataforma** | `AdminUser` con `is_superuser` y/o `admin.docs.approve`. Aprueba o deniega. Sin su OK el cambio **no es visible**. |
| **Solicitud de cambio** | Paquete: versión de trabajo + motivo. Estados `pending` → `approved` \| `rejected`. |
| **Versión publicada** | Única que ven lectores e IAs. |
| **Versión de trabajo** | `.md` en MinIO que el tecnológico edita. Invisible hasta aprobar. |
| **`feature_key`** | Clave del catálogo (`orders.create`, `admin.tenants.view`, …). Misma que `session.features`. |
| **Audiencia** | `public` \| `admin` \| `wms`. |
| **Kind** | `manual` \| `architecture` \| `technical` \| `plan` \| `vision`. |

---

## 3. Tres mundos y fronteras

```
core/        transversal (errors, storage, auth cookies, AI ports)
platform/    admin SaaS (schema public)
client/      WMS por tenant (schema empresa)
handbook/    documentación de plataforma (schema public, ACL por lector)
```

`handbook/` **no** vive dentro de `platform/`: lo leen anónimos, clientes y
admins. El CMS sí exige cookie `access_admin`.

El paquete Python se llama `handbook` para no chocar con `docs/` de ingeniería
ni con `platform.features.documents`. La URL pública puede ser `/api/v1/docs/`.
El frontend previsto es `base-docs-web` (Angular 18 + `base-web-lib`).

Features hexagonales:

```
handbook/features/catalog/           árbol (espacios, secciones)
handbook/features/page/              artículo + versiones .md
handbook/features/change_request/    solicitudes de cambio
handbook/features/ingest/            chunks / embeddings
```

---

## 4. Audiencias y ACL de lectura

Evaluación **en el use case**, no solo en la UI. Lectura denegada → `HBK_001`
(no filtrar existencia).

| Audiencia | Anónimo | Cliente (tenant) | Admin de plataforma |
|-----------|---------|------------------|---------------------|
| `public` publicado | sí | sí | sí |
| `admin` publicado | no | no | superuser **o** `feature_key` en sesión admin |
| `wms` publicado | no | `feature_key` en `session.features` (rol ∩ plan) | **todo** el WMS |
| draft / versión de trabajo / solicitud pendiente | no | no | staff handbook (`propose` o `approve`) |

Un usuario **Administrator de la empresa** es lector WMS, nunca editor del
handbook.

---

## 5. Gobierno de cambios (solicitud + aprobación)

Nadie publica directo al lector. Ni el tecnológico ni un atajo de CMS.

```
Admin tecnológico
  edita versión de trabajo (MinIO)     ← no visible
  envía solicitud + motivo             ← status=pending
                    │
                    ▼
Administrador de Plataforma
  aprueba  → versión de trabajo pasa a publicada; ingest de chunks
  deniega  → se descarta la versión de trabajo; lo publicado no cambia
```

Reglas:

1. **Quién edita.** Solo `AdminUser` con `admin.docs.propose`. El Administrator
   del cliente no entra al CMS.
2. **Quién aplica.** Solo Administrador de Plataforma (`is_superuser` o
   `admin.docs.approve`). Aprobar es el único camino a `published`.
3. **Motivo obligatorio** al enviar (texto de negocio, no UUID). Sin motivo no
   hay solicitud.
4. **Una solicitud pendiente por página.** No apilar dos `pending` sobre el
   mismo artículo.
5. **Mientras está `pending`** la versión de trabajo queda congelada: no se
   sigue editando esa solicitud. El tecnológico puede retirar/cancelar solo si
   el plan de UI lo permite; el default es esperar la decisión.
6. **Denegación** borra el objeto de trabajo en MinIO y deja la solicitud
   `rejected` (auditoría). El lector sigue viendo la última versión aprobada.
7. **Aprobación** apunta `published_version_id` a la versión de trabajo,
   dispara ingest (best-effort) y deja la solicitud `approved`.
8. El **superuser** puede proponer y aprobar (tiene todas las claves). Puede
   autoaprobar; el rastro de la solicitud sigue existiendo.

Claves de producto (catálogo `AdminFeature`, **no** en migraciones):

- `admin.docs.propose` — redactar y enviar solicitud.
- `admin.docs.approve` — aprobar o denegar.

Códigos: `HBK_006` motivo inválido, `HBK_007` no está pendiente, `HBK_008` no
puede proponer, `HBK_009` no puede aprobar, `HBK_010` ya hay una pendiente.

---

## 6. Almacenamiento PostgreSQL + MinIO

Patrón ya usado en avatars, ilustraciones y PDFs: **metadatos en PG, bytes en
MinIO**.

| Qué | Dónde |
|-----|-------|
| Árbol, slugs, audience, feature_key, kind, locale, orden | PostgreSQL `public` |
| Solicitudes (motivo, estado, autores, versiones) | PostgreSQL `public` |
| Cuerpo `.md` versionado e imágenes | MinIO, prefix `handbook/`, bucket privado (`DOCUMENTS_DEFAULT_BUCKET`) |
| Búsqueda / embeddings | PG (`tsvector` y más adelante `pgvector` en `doc_chunks`) |
| Lectura caliente | opcional `published_markdown` denormalizado; MinIO sigue siendo SoT de versiones |

Object keys: `handbook/pages/{page_id}/{version_id}.md`,
`handbook/assets/{page_id}/{filename}`. Lectura de privados vía URL prefirmada
o proxy autenticado. No política anónima al estilo avatars.

---

## 7. APIs para humanos e IAs

Mismo filtrado ACL. Host público; cookie admin o client (`schema_name` del JWT
para cargar al usuario tenant).

Lectura (publicado):

- `GET /api/v1/docs/tree/`
- `GET /api/v1/docs/pages/{slug}/`
- `GET /api/v1/docs/search/?q=`
- `POST /api/v1/docs/ai/retrieve/` — chunks para agentes

CMS (admin tecnológico / Administrador de Plataforma):

- Working copy y metadatos de página
- `POST .../change-requests/` (motivo)
- `POST .../change-requests/{id}/approve|reject/`

assistant: tool `search_platform_docs` con la ACL del usuario del chat. El
modelo no lee MinIO: el use case filtra y luego trae texto.

Hasta tener embedder real: retrieve por `tsvector`. El índice de docs es
**global en `public`** (excepción documentada al “pgvector por tenant”: no hay
datos de empresa en el corpus).

---

## 8. Frontend

**Nueva app Angular 18 `base-docs-web`** (`docs.base.local`, puerto 4202):
lector + CMS, `wa-auth-web` con `X-Auth-Context` dinámico, controles de
`wa-components-web`, editor markdown en la lib.

No Astro/Starlight (no cubre CMS ni ACL). No meter el CMS en `base-admin-web`
(los lectores públicos y de cliente no pertenecen al portal admin).

Landing: `PUBLIC_DOCS_URL`. Toolbar client `manual` y sidebar admin: deep links.

El CMS muestra “Enviar solicitud” (tecnológico) y cola “Pendientes de aprobar”
(Administrador de Plataforma). El lector nunca ve chrome de CMS ni copys de
trabajo.

---

## 9. Mapa de fases

| Fase | Nombre | Entregable | Depende de |
|:----:|--------|------------|------------|
| **0** | Cimientos | Paquete `handbook/`, apps, auth dual, storage keys | — |
| **1** | ACL + solicitudes | Viewer, `can_view` / `can_propose` / `can_approve`, máquina de estados, use cases | Fase 0 |
| **2** | Persistencia | Modelos, migraciones, MinIO upload, repos Django | Fase 1 |
| **3** | APIs | `RequestBody`/`QueryFilter`, lectura + CMS, URLs public/tenant | Fase 2 |
| **4** | Frontend | `base-docs-web` lector + CMS + solicitudes | Fase 3 |
| **5** | IA | Ingest, retrieve, tool assistant | Fases 3–4 |

No se implementa la fase N+1 sin cerrar la N (DoD). Tests unitarios del
dominio desde la Fase 0/1; API/integración desde la 2–3.

```bash
pytest handbook/tests/unit/ -m unit
```

---

## 10. Bitácora de decisiones

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-08-29 | Tercer mundo `handbook/` (no `docs/` ni `documents`) | Choque con `docs/` de ingeniería y con plantillas PDF |
| 2026-08-29 | PG metadatos + MinIO `.md` | Mismo patrón que storage actual; ACL consultable |
| 2026-08-29 | `feature_key` = clave de login, no catálogo `docs.*` paralelo | Una sola fuente de entitlement |
| 2026-08-29 | Admin de plataforma ve todo el WMS; cliente filtra por sesión | Pedido de producto |
| 2026-08-29 | Índice RAG del handbook en schema `public` | Corpus de plataforma, no datos de tenant |
| 2026-08-29 | Frontend Angular 18 `base-docs-web` | CMS + ACL + `base-web-lib`; no Astro |
| 2026-08-29 | Publicar solo vía solicitud aprobada | El tecnológico redacta; el Administrador de Plataforma aplica o descarta |
| 2026-08-29 | `admin.docs.propose` vs `admin.docs.approve` | El Administrator de cliente no edita; el superuser aprueba |
