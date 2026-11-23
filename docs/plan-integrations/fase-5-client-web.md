# FASE 5 — Autogestión IT del cliente (`base-client-web`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 4](fase-4-admin-web.md) · **Fase 5** · Siguiente → [Fase 6](fase-6-prosandbox.md)

> **Continuidad — qué se hizo en la Fase 4.** Gobierno platform en admin. La Fase 5
> entrega la experiencia para el **admin IT del cliente**: configurar conexiones
> con sus ERPs y aplicaciones, mapeos, pruebas y monitoreo — sin acceso a lógica
> de operación de bodega.

**Objetivo:** sección dedicada en `base-client-web` bajo módulo `integrations`,
visible solo para usuarios con rol IT y entitlement `integrations.*` activo.

**Prerequisito backend:** APIs tenant de Fase 2 + permiso `integrations.manage_connections`.

### Ubicación en cliente

```
src/app/feature/integrations/
├── integrations.module.ts
├── integrations-routing.module.ts
├── models/
├── services/
│   └── integrations.service.ts
└── pages/
    ├── connections-list/
    ├── connection-wizard/       # crear/editar conexión
    ├── connection-detail/       # salud, último sync, acciones
    ├── mapping-editor/          # pedidos (MVP)
    ├── sync-history/
    └── integration-logs/        # reutiliza o enlaza integration-logs feature
```

Ruta sugerida: `/settings/integrations` o `/integrations` (alineado a IT, no operadores PDA).

### Flujo principal — Wizard de conexión

```
1. Elegir conector (SAP | SIESA | App webhook)  ← catálogo activo
2. Elegir entorno (CLIENT_TEST | CLIENT_PROD)   ← PROSANDBOX no visible en prod
3. Completar config (URL, company code, …)      ← driven by config_schema
4. Ingresar credenciales (campos password)      ← nunca se re-muestran
5. Test connection                            ← obligatorio antes de guardar ACTIVE
6. (Opcional) Configurar mapeo pedidos
7. (Opcional) Dry-run sync
8. Activar + schedule cron
```

### Pantallas

| Pantalla | Funciones |
|----------|-----------|
| **Lista conexiones** | estado, entorno, último sync, acciones (sync manual, pausar) |
| **Detalle** | config (sin secretos), health, errores recientes |
| **Mapeo pedidos** | editor tabla source→target; validación client-side básica |
| **Historial sync** | SyncRuns con stats y enlace a logs |
| **Logs** | filtro por conexión/sistema; usa API logging integration existente |

### Permisos y UX

- Guard: `integrations.manage_connections` + feature flag de plan.
- Operadores de bodega **no** ven este módulo.
- Estados loading/error/success en cada acción async (test, dry-run, sync).
- Confirmación antes de sync manual en PROD.

### Documentación embebida (mínima Fase 5)

- Panel lateral con: qué necesita el cliente para conectar SAP/SIESA (URL, usuario).
- Enlace a documentación API para **aplicaciones del cliente** (webhook inbound).
- Sin i18n complejo inicialmente: en/es en archivos i18n.

### Acoplamiento futuro

- [plan-ia fase 6](../../plan-ia/fase-6-integraciones-ia.md): botón "Sugerir mapeo con IA"
  en `mapping-editor` (cuando exista backend).

**Actividades:**

- [ ] Crear módulo `feature/integrations` en base-client-web.
- [ ] Servicio HTTP APIs tenant `/api/v1/integrations/`.
- [ ] Pantalla lista + wizard conexión.
- [ ] Integrar test connection y dry-run en UI.
- [ ] Editor de mapeo pedidos (MVP).
- [ ] Historial sync runs.
- [ ] Vista logs (integración con `integrations.integration-logs` feature).
- [ ] Guards rol IT + entitlement.
- [ ] i18n básico en/es.
- [ ] Documentación inline mínima por conector.

**Definición de Done de la Fase 5:**

- [ ] Admin IT crea conexión SAP en CLIENT_TEST, pasa test connection.
- [ ] Configura mapeo y ejecuta dry-run desde UI.
- [ ] Ejecuta sync manual y ve resultado en historial.
- [ ] Credenciales no se muestran tras guardar (solo rotación).
- [ ] Usuario operativo sin permiso IT no accede al módulo.
