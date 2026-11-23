# FASE 6 — ProSandbox interno (`wa-prosandbox-web` + `base-prosandbox`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 5](fase-5-client-web.md) · **Fase 6**

> **Continuidad — qué se hizo en las Fases 1–5.** Tubería, MVP sync pedidos,
> tests, UI admin y cliente. La Fase 6 crea el **entorno simulado** de sistemas
> externos (SAP, SIESA) para desarrollo y pruebas de latencia/integrabilidad
> **solo dentro de la base** — nunca desplegado en producción.

**Objetivo:** dos proyectos independientes que emulan APIs de ERPs con escenarios
configurables (éxito, timeout, error 500, payloads inconsistentes), usables como
`environment=PROSANDBOX` en conexiones de desarrollo.

**Estado:** **pendiente** hasta tener contratos HTTP estables de SAP/SIESA y/o
acuerdos con proveedores. La Fase 2 puede usar stubs; esta fase los reemplaza
por simuladores realistas.

### Arquitectura

```
┌─────────────────────┐         HTTP          ┌──────────────────────┐
│  base        │ ◄──────────────────► │  base-prosandbox   │
│  (dev only)         │   PROSANDBOX URL     │  simula SAP / SIESA  │
└─────────────────────┘                      └──────────┬───────────┘
                                                        │
┌─────────────────────┐         HTTP          ┌─────────▼───────────┐
│  wa-prosandbox-web  │ ────────────────────► │  escenarios / admin │
│  (dev only)         │   configurar          │  latencia, errores  │
└─────────────────────┘                       └──────────────────────┘
```

### `base-prosandbox` (backend simulador)

Stack sugerido: mismo ecosistema Python (FastAPI o Django ligero) para velocidad.

```
base-prosandbox/
├── app/
│   ├── main.py
│   ├── providers/
│   │   ├── sap/
│   │   │   ├── routes.py      # OData-like / REST pedidos
│   │   │   └── fixtures/
│   │   └── siesa/
│   │       ├── routes.py
│   │       └── fixtures/
│   ├── scenarios/             # delay, 500, partial data
│   └── middleware/            # auth básica simulada
└── tests/
```

**Endpoints mínimos (contrato compartido con conectores reales):**

| Proveedor | Operación | Método |
|-----------|-----------|--------|
| SAP | Listar pedidos pendientes | GET |
| SAP | Confirmar recepción pedido | POST |
| SAP | Crear/actualizar estado outbound | PATCH |
| SIESA | Equivalentes según API real | TBD |

Los contratos exactos se documentan en `docs/plan-integrations/contracts/` cuando
se definan con el primer cliente o documentación oficial.

### `wa-prosandbox-web` (frontend control)

Panel interno la base para:

- Seleccionar proveedor (SAP / SIESA).
- Activar escenario: `happy_path`, `slow_3s`, `error_500`, `malformed_payload`.
- Ver requests recibidos (útil para debug de conectores).
- Reset fixtures.

**No** expuesto a clientes finales.

### Integración con base

- En `local.py` / dev: `PROSANDBOX_BASE_URL=http://localhost:9xxx`.
- Conexiones con `environment=PROSANDBOX` solo permitidas si
  `DEBUG=True` o `INTEGRATIONS_ALLOW_PROSANDBOX=True` (settings).
- CI: tests de integración opcionales contra prosandbox-msv en pipeline.

### Relación con entornos del cliente

| Entorno | Dónde corre |
|---------|-------------|
| PROSANDBOX | base-prosandbox (solo dev de la base) |
| CLIENT_TEST | Infra del cliente |
| CLIENT_PROD | Infra del cliente |

El flujo de promoción TEST → PROD es responsabilidad del admin IT (Fase 5);
prosandbox no participa en UAT del cliente.

**Actividades:**

- [ ] Crear repositorio/proyecto `base-prosandbox`.
- [ ] Definir contratos HTTP en `docs/plan-integrations/contracts/sap-orders.md`.
- [ ] Definir contratos HTTP en `docs/plan-integrations/contracts/siesa-orders.md`.
- [ ] Implementar rutas SAP pedidos + fixtures.
- [ ] Implementar rutas SIESA pedidos + fixtures.
- [ ] Motor de escenarios (latencia, errores).
- [ ] Crear `wa-prosandbox-web` con panel de control.
- [ ] Cablear `INTEGRATIONS_ALLOW_PROSANDBOX` en base.
- [ ] Tests e2e dev: core-mon → prosandbox-msv sync pedidos.
- [ ] Documentar arranque local en README de prosandbox.

**Definición de Done de la Fase 6:**

- [ ] Desarrollador puede apuntar conexión PROSANDBOX a prosandbox-msv y completar sync pedidos.
- [ ] Escenario `slow_3s` verifica timeout/retry del runner.
- [ ] Escenario `error_500` verifica circuit breaker y sync_run FAILED.
- [ ] Proyectos **no** incluidos en despliegue de producción la base.
- [ ] Contratos documentados y alineados con conectores SAP/SIESA de Fase 2.
