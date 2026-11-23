# FASE 5 — IA (retrieve + assistant)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 4](fase-4-frontend.md) · **Fase 5**

> **Continuidad.** Corpus publicado y APIs de lectura. El assistant hoy no tiene
> RAG (`IEmbedder` es fake).
>
> **Fuera de esta fase:** OCR / document extractor de facturas (otro cubo de
> `plan-ia`).

**Objetivo:** que assistant (y otras IAs) consulten **solo** markdown
publicado, con la ACL del usuario del chat. Ingest al **aprobar**, no al
guardar working copy.

**Actividades:**

- [ ] Chunking al approve; borrar chunks de la versión anterior.
- [ ] `POST /docs/ai/retrieve/` con el mismo `can_view`.
- [ ] Tool `search_platform_docs` en el whitelist del assistant.
- [ ] Degradación: `tsvector` si el embedder sigue en fake.
- [ ] `pgvector` en `public` (`doc_chunks`) cuando haya embedder real.
- [ ] Tests: retrieve no devuelve una working copy ni un artículo `wms` a un
      cliente sin la `feature_key`.

**Definición de Done de la Fase 5:**

- [ ] Aprobar dispara ingest; denegar no indexa el descarte.
- [ ] El assistant cita/paráfrasis solo chunks recuperados (prompt: no inventar SOP).
