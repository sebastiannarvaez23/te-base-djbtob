# FASE 4 — Instrumentación de datos ML-ready

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 3](fase-3-copiloto-agentico.md) · **Fase 4** · Siguiente → [Fase 5](fase-5-ml-predictivo.md)

> **Continuidad — qué se hizo en la Fase 3.** La Fase 3 construyó el **base
> Assistant** (copiloto agéntico sobre **SLM nativo**): registro de tools sobre
> use cases, bucle de agente con aislamiento por tenant, guardrails,
> confirmación de escrituras, streaming y cableado del chat en `base-client-web`.
> Hasta aquí, **todo lo entregado (Fases 0b–3, y también la 6) vive sin datos
> históricos de ML**. La Fase 4 ataca esa carencia: no produce features de IA
> visibles, sino que **instrumenta la captura de datos ML-ready** mientras se
> construye el core operativo, para habilitar el cubo 3 más adelante. Debe
> arrancar **en paralelo, cuanto antes**.

**Objetivo:** garantizar que, mientras se construye el core operativo del WMS,
se **capturen los datos y eventos** necesarios para que el ML predictivo (Fase 5)
sea posible más adelante. Es la inversión más estratégica del plan.

**Descripción detallada:** El cubo 3 no existe sin historial de calidad. Esta fase
**no produce features de IA visibles**; produce la materia prima. Debe arrancar lo
antes posible y avanzar **en paralelo** con la construcción de cada módulo
operativo (orders, reception, picking, packing, dispatch). Aprovecha el sistema de
`client/features/logging/` ya existente y lo extiende con captura orientada a
features de ML (marcas de tiempo por evento, resultados reales para poder comparar
contra predicciones, etc.).

**Actividades:**

- [ ] Definir el **catálogo de eventos** a capturar por módulo operativo (creación,
      transiciones de estado, tiempos de inicio/fin de tareas, cantidades,
      desviaciones).
- [ ] Asegurar **marcas de tiempo** consistentes y granularidad suficiente para
      series temporales (demanda, tiempos de proceso).
- [ ] Capturar **resultados reales** (ground truth) que luego servirán para
      entrenar y evaluar (ETA real vs prometido, tiempo real de picking, etc.).
- [ ] Registrar contexto suficiente para *features* (SKU, ubicación, operario,
      turno, transportista, zona), respetando PII.
- [ ] Definir política de **retención** de datos históricos para ML (por tenant).
- [ ] Diseñar el mecanismo de **exportación/vista analítica** por schema (sin
      mezclar tenants) que consumirá el pipeline de entrenamiento.
- [ ] Documentar el esquema de datos ML-ready para el equipo.
- [ ] Verificar que la instrumentación **no degrada** el rendimiento del hot path
      (best-effort, asíncrono como el sistema de incidencias).

**Definición de Done de la Fase 4:**

- [ ] Cada módulo operativo nuevo nace instrumentado (checklist en su Definición
      de Done).
- [ ] Existe una vista/exportación de datos históricos por tenant lista para
      alimentar entrenamiento.
