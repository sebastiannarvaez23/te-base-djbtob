# FASE 1 — ACL y solicitudes de cambio (dominio)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · Anterior → [Fase 0](fase-0-cimientos.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-persistencia.md)

> **Continuidad.** La Fase 0 dejó `can_view` / `can_manage` genérico y un único
> `admin.docs.manage`. El producto exige **dos actores de plataforma** y que
> **nada publicado** aparezca sin aprobación.
>
> **Fuera de esta fase:** tablas, MinIO upload, HTTP, UI.

**Objetivo:** codificar en dominio (sin BD) quién lee, quién redacta, quién
aprueba, y la máquina de estados de la solicitud de cambio.

### Actores

| Actor | Origen | Clave | Puede |
|-------|--------|-------|-------|
| Lector | anónimo / client / admin | las de la sección | ver **publicado** |
| Admin tecnológico | `AdminUser` (no tenant) | `admin.docs.propose` | editar working copy, **enviar** solicitud con motivo |
| Administrador de Plataforma | `AdminUser` `is_superuser` y/o `admin.docs.approve` | `admin.docs.approve` | **aprobar** (publica) o **denegar** (descarta) |
| Administrator de cliente | tenant `Administrator` | — | solo lectura WMS según su sesión |

### Máquina de estados

```
working copy (no visible)
    --submit(reason)--> pending
                            --approve--> approved + published = working
                            --reject-->  rejected + working discarded
```

Una sola solicitud `pending` por página. Motivo obligatorio (10–2000
caracteres). Use cases: `SubmitChangeRequest`, `ApproveChangeRequest`,
`RejectChangeRequest`. El repositorio aplica o descarta bytes; el use case no
habla con MinIO.

**Actividades:**

- [x] Separar `can_propose` / `can_approve` / staff (`can_manage` = cualquiera de los dos).
- [x] Drafts y working copy solo visibles a staff; lectores solo `published`.
- [x] Feature `handbook.features.change_request` (schemas, puerto, use cases).
- [x] Códigos `HBK_006`–`HBK_010` + `ES_OVERRIDES`.
- [x] Store en memoria para tests (sin PG).
- [x] Tests: cliente no propone; tecnológico no publica; approve publica;
      reject descarta; motivo vacío; pending duplicado; anónimo no ve draft.

**Definición de Done de la Fase 1:**

- [x] Un tecnológico no puede dejar contenido `published` sin pasar por approve.
- [x] Un Administrator de cliente (`kind=client`) no propone ni aprueba.
- [x] `pytest handbook/tests/unit/ -m unit` en verde.
