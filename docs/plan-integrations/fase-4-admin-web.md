# FASE 4 — Administración plataforma (`base-admin-web`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 3](fase-3-tests.md) · **Fase 4** · Siguiente → [Fase 5](fase-5-client-web.md)

> **Continuidad — qué se hizo en la Fase 3.** Suite unitaria del núcleo y del MVP
> sync pedidos. La Fase 4 expone **gobierno de plataforma** para que el equipo
> la base administre el catálogo de conectores, límites comerciales y soporte
> cross-tenant — sin sustituir la autogestión del cliente IT (Fase 5).

**Objetivo:** pantallas en `base-admin-web` para CRUD del catálogo de conectores,
monitoreo de salud de integraciones, y acciones de soporte (ver conexiones,
pausar, ver logs agregados) — consumiendo APIs `platform/integrations/`.

**Prerequisito backend:** Fase 2 APIs platform estables.

### Módulo Angular propuesto

```
src/app/feature/integrations/
├── integrations.module.ts
├── integrations-routing.module.ts
├── models/
│   ├── connector-definition.model.ts
│   └── integration-health.model.ts
├── services/
│   └── integrations-admin.service.ts
└── components/
    ├── connector-catalog-list/
    ├── connector-catalog-form/
    ├── integration-health-dashboard/
    └── tenant-connections-support/    # vista soporte (read-only + pause)
```

Registrar ruta bajo menú administración existente (patrón `feature/admin`).

### Pantallas

#### 1. Catálogo de conectores

| Acción | Detalle |
|--------|---------|
| Listar | SAP, SIESA, futuros proveedores/apps |
| Crear / editar | key, kind, capabilities, config_schema (JSON editor) |
| Activar / desactivar | `is_active` |
| Versionar | campo `version` visible |

Componentes reutilizables de `base-web-lib` (tablas, formularios).

#### 2. Dashboard de salud (cross-tenant)

| Widget | Fuente API |
|--------|------------|
| Conexiones degradadas / error | `GET /platform/integrations/health/` |
| Sync runs fallidos (24h) | agregado |
| Top errores por conector | agregado |

Solo lectura; sin credenciales en claro.

#### 3. Vista soporte por tenant

| Acción | Permiso |
|--------|---------|
| Ver conexiones del tenant | rol soporte |
| Ver historial sync (sin secretos) | rol soporte |
| Pausar conexión en nombre del cliente | rol soporte + auditoría |
| **No** editar credenciales | — |

### Acoplamiento con billing / access

- Al editar plan de empresa, mostrar features `integrations.*` habilitadas
  (ya existe patrón en admin de features/roles).
- Opcional: límite de conexiones activas por plan (parámetro o entitlement).

### i18n

- Claves en `assets/i18n/` (en/es) — empezar simple, sin wizard.

**Actividades:**

- [ ] Crear módulo `feature/integrations` en base-admin-web.
- [ ] Servicio HTTP hacia `platform/integrations/catalog/`.
- [ ] Pantalla listado + formulario catálogo.
- [ ] Pantalla dashboard salud.
- [ ] Pantalla soporte tenant (conexiones read-only + pause).
- [ ] Permisos de ruta (guard admin).
- [ ] i18n básico en/es.
- [ ] Tests de componente/servicio (si el proyecto los usa en admin).

**Definición de Done de la Fase 4:**

- [ ] Admin de la base puede activar/desactivar SAP y SIESA en catálogo.
- [ ] Dashboard muestra conexiones en ERROR sin exponer secretos.
- [ ] Soporte puede pausar una conexión problemática con traza de auditoría.
- [ ] UI sigue patrones Smart/Dumb y servicios `*Service` del proyecto admin.
