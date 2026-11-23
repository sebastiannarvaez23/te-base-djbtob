# FASE 4 — Frontend `base-docs-web`

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 3](fase-3-apis.md) · **Fase 4** · Siguiente → [Fase 5](fase-5-ia.md)

> **Continuidad.** APIs estables. El lector y el CMS viven en **la misma** app
> Angular 18, no en landing ni solo en admin-web.
>
> **Fuera de esta fase:** embeddings / tool del assistant.

**Objetivo:** app `base-docs-web` con lector (ACL), login dual y CMS de
solicitudes. Controles de `wa-components-web` (no `<button>`/`<select>`
nativos). Editor markdown nuevo en `base-web-lib`.

**Actividades:**

- [ ] Scaffold Angular 18, puerto 4202, `wa-auth-web` con contexto admin|client.
- [ ] Lector: árbol, página, búsqueda, i18n es/en.
- [ ] CMS `/manage`: solo cookie admin. Tecnológico: editar + “Enviar solicitud”
      (motivo obligatorio). Administrador de Plataforma: cola pendiente,
      aprobar / denegar.
- [ ] Preview “ver como” anónimo / cliente con keys / admin.
- [ ] Deep links desde landing, sidebar admin, toolbar client `manual`.
- [ ] Verificar en navegador el flujo submit → approve (visible) y reject
      (no visible).

**Definición de Done de la Fase 4:**

- [ ] Un tecnológico no tiene botón “Publicar”.
- [ ] Tras approve, el lector anónimo/cliente ve el markdown nuevo.
- [ ] Tras reject, el lector sigue viendo la versión anterior.
