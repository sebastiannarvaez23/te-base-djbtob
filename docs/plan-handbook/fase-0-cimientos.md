# FASE 0 — Cimientos (`handbook/`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 0** · Siguiente → [Fase 1](fase-1-acl-y-solicitudes.md)

> **Continuidad.** Primera fase de construcción. Prerequisito: el
> [resumen teórico](00-resumen-teorico.md) y los mundos `platform/` / `client/`.
>
> **Fuera de esta fase:** modelos Django, HTTP, CMS, MinIO real, IA.

**Objetivo:** montar el paquete `handbook/` como tercer mundo, con `core` de
constantes/storage/auth dual y tres features hexagonales vacías de persistencia,
registradas en `SHARED_APPS`.

**Actividades:**

- [x] Crear `handbook/` (`core/`, `features/`, `tests/`) alineado a platform/client.
- [x] Constantes de audiencia, kind, status, prefix MinIO.
- [x] `HandbookAccessAuthentication` (cookie admin o client + `schema_name`).
- [x] Helpers de object key (`markdown_object_key`, `asset_object_key`).
- [x] Apps `catalog`, `page`, `ingest` (hexagonal, sin modelos de negocio).
- [x] Códigos `HBK_001`–`HBK_005` + `ES_OVERRIDES`.
- [x] `SHARED_APPS` + `pytest.ini` `handbook/tests`.
- [x] Tests de ACL de lectura (audiencias) y storage keys.

**Definición de Done de la Fase 0:**

- [x] `python manage.py check` en verde con las apps nuevas.
- [x] Tests unitarios de `handbook/tests/unit/core/` en verde.
- [x] Ninguna tabla nueva (sin seed, sin migración de datos).
