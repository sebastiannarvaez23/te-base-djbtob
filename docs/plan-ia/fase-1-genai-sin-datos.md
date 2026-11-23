# FASE 1 — Primeras features GenAI (sin datos)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 0b](fase-0b-runtime-slm.md) · **Fase 1** · Siguiente → [Fase 2](fase-2-optimizacion-or.md)

> **Continuidad — qué se hizo en las Fases 0 / 0b.** La Fase 0 construyó el
> módulo transversal `core/ai/` (puertos, `fake`, adaptador gestionado opcional,
> observabilidad, caché, PII, `complete_or`, `AI_*`). La Fase 0b añade el
> **runtime SLM nativo**, el adaptador `local` y el kill-switch de infra. **Con
> esa tubería**, la Fase 1 construye las primeras features de negocio de GenAI.
> Para texto real en entorno local/staging se recomienda `AI_PROVIDER=local`;
> en CI se usa `fake`. El copiloto conversacional (assistant) es la Fase 3.

**Objetivo:** entregar valor visible con casos de uso de IA generativa que **no
requieren datos históricos**, validando la tubería de punta a punta sobre el
SLM (o `fake` en tests).

**Descripción detallada:** Features de los cubos 1 y 2. No entrenan nada; usan
prompts + el modelo detrás de `IChatModel`. Sirven como quick wins y como
ensayo de degradación cuando el runtime está off. Cada una sigue la estructura
hexagonal completa de una feature.

### 1.1 Resumen operativo inteligente (`smart-day-summary`) — Cubo 1

Genera una narrativa en lenguaje natural del estado de la bodega del día (órdenes
pendientes, inventario crítico, alertas), a partir de métricas ya existentes.

- [ ] Diseñar el prompt de resumen (plantilla + variables de métricas; contexto
      corto apto para SLM).
- [ ] Crear la feature con estructura hexagonal (`domain/application/infrastructure/presentation`).
- [ ] Use case `GenerateDaySummaryUseCase(model: IChatModel, repository)`.
- [ ] Endpoint `GET /api/v1/dashboard/day-summary/` (JWT cliente, `IsCompanyMember`).
- [ ] Manejo de degradación: si el SLM/runtime falla o IA off, devolver un
      resumen básico con reglas (no romper el dashboard).
- [ ] Tests unit (con `FakeChatModel`) + API.

### 1.2 Lectura de documentos de entrada (extracción) — Cubo 2

Sube una factura / orden de compra / packing list (PDF o foto) y el sistema
extrae los datos estructurados (proveedor, referencias, cantidades, lotes).

- [ ] Definir el schema de salida estructurado (Pydantic) por tipo de documento.
- [ ] Use case `ExtractDocumentUseCase(extractor: IDocumentExtractor)`.
- [ ] Endpoint de carga → extracción (usar `core/storage/` para el archivo,
      Celery si el documento es pesado).
- [ ] Validación y corrección: el resultado extraído se presenta para revisión
      humana antes de persistir (human-in-the-loop).
- [ ] Guardrails: nunca persistir automáticamente montos/cantidades sin
      confirmación en esta etapa.
- [ ] Decidir backend de extracción (SLM multimodal local vs managed puntual) y
      anotar en bitácora; no bloquea 1.1 ni la Fase 3.
- [ ] Tests con documentos de ejemplo.

### 1.3 Clasificación automática de SKU nuevo — Cubo 1

Dada la descripción libre de un producto, el modelo propone categoría, unidad de
medida y restricciones (frágil, refrigerado, peligroso).

- [ ] Use case `ClassifySkuUseCase(model: IChatModel)`.
- [ ] Integrarlo como sugerencia (no obligatorio) en el alta de referencias.
- [ ] Prompt corto y salida estructurada (JSON) apta para SLM.
- [ ] Tests.

**Definición de Done de la Fase 1:**

- [ ] Al menos `smart-day-summary` está disponible tras feature-flag / `AI_ENABLED`.
- [ ] Todas las features degradan con elegancia si el runtime está off o falla.
- [ ] El uso (tokens/latencia/modelo) queda registrado por tenant.
