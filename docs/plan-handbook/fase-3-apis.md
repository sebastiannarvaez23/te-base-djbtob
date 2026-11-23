# FASE 3 — APIs HTTP

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 2](fase-2-persistencia.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-frontend.md)

> **Continuidad.** Repos reales existen. Falta presentación: `RequestBody` /
> `QueryFilter`, `wrap_response`, auth dual, registro en `base/urls.py` y
> `base/urls_public.py`.
>
> **Fuera de esta fase:** Angular, RAG.

**Objetivo:** endpoints de lectura (publicado) y CMS (working copy +
solicitudes) con la ACL de la Fase 1.

**Actividades:**

- [ ] Lectura: tree, page by slug, search (`tsvector` si ya hay texto denormalizado).
- [ ] CMS: CRUD de nodos/páginas (working copy), listado de solicitudes.
- [ ] `POST` submit (motivo), approve, reject (`review_note` opcional al denegar).
- [ ] `HandbookAccessAuthentication` + `AllowHandbookRead` / proposer / approver.
- [ ] CORS / host `docs.base.local` (puerto 4202) cuando exista el frontend.
- [ ] Tests API: anónimo solo public; cliente WMS filtrado; submit 403 si es tenant;
      approve 403 si es tecnológico sin `approve`.

**Definición de Done de la Fase 3:**

- [ ] Un GET de página anónima no devuelve working copy ni solicitudes.
- [ ] El único POST que cambia lo que ve el lector es **approve**.
- [ ] Validación estricta: sin `request.data` crudo.
