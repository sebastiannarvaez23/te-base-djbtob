# FASE 2 — Persistencia (PostgreSQL + MinIO)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 1](fase-1-acl-y-solicitudes.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-apis.md)

> **Continuidad.** El dominio de ACL y solicitudes ya está testeado en memoria.
> Esta fase materializa tablas en `public` y bytes en MinIO.
>
> **Fuera de esta fase:** HTTP de producto, frontend, embeddings.

**Objetivo:** modelos + migraciones **solo de esquema**, repos Django,
`IStorageService` para `.md`/assets, y comando (no migración) para
`AdminFeature` `admin.docs.propose` / `admin.docs.approve`.

### Tablas (borrador)

- `handbook_nodes` — árbol, audience, feature_key, kind, locale, sort_order
- `handbook_pages` — slug, title, `published_version_id`, published_markdown opcional
- `handbook_versions` — bucket, object_key, sha256, created_by
- `handbook_change_requests` — page, working_version, reason, status, proposed_by, reviewed_by, review_note, timestamps

FK `on_delete=DO_NOTHING` salvo tablas internas de join. UUID PK.

**Actividades:**

- [ ] Modelos en `catalog` / `page` / `change_request` y migraciones de esquema.
- [ ] Repos Django que implementan los puertos de la Fase 1.
- [ ] Upload/replace/delete de `.md` vía `MinioStorageService`.
- [ ] Al aprobar: actualizar `published_version_id` + opcional denormalizar markdown.
- [ ] Al denegar: `delete_file` de la versión de trabajo.
- [ ] Management command `ensure_handbook_admin_features` (no `RunPython` en migraciones).
- [ ] Tests de repositorio (integration) del ciclo submit → approve/reject.

**Definición de Done de la Fase 2:**

- [ ] `migrate_schemas` aplica sin seed de artículos.
- [ ] Approve deja un GET de página (vía repo) con el markdown nuevo; reject no.
- [ ] Ningún `.md` huérfano documentado: reject borra el objeto de trabajo.
