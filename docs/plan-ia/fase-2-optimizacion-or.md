# FASE 2 — Optimización operativa (OR)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 1](fase-1-genai-sin-datos.md) · **Fase 2** · Siguiente → [Fase 3](fase-3-copiloto-agentico.md)

> **Continuidad — qué se hizo en la Fase 1.** La Fase 1 entregó las primeras
> features de IA generativa **sin datos históricos** (resumen operativo del día,
> extracción de documentos y clasificación de SKU), validando la tubería de las
> Fases 0/0b: prompts reales contra el **SLM nativo** (o `fake` en CI),
> degradación cuando el runtime está off y registro de uso por tenant. **La Fase 2
> cambia de cubo:** pasa de GenAI (cubos 1/2) a la **optimización matemática
> (cubo 4)**, que tampoco necesita datos históricos ni runtime de lenguaje — corre
> en tu propia infraestructura. Es terreno de ingeniería pura.

**Objetivo:** entregar las optimizaciones matemáticas del cubo 4. No usan IA
externa ni datos históricos: son algoritmos (investigación de operaciones) que
corren en tu propia infraestructura. Es terreno de ingeniería pura y de alto
impacto operativo.

**Descripción detallada:** Estas features resuelven problemas de combinatoria y
ruteo con solvers (p. ej. OR-Tools). Requieren solo el **estado actual** (layout de
bodega, órdenes activas, dimensiones de SKU), no historial. Se modelan también con
puertos/adaptadores (`IRouteOptimizer`, `ISlottingEngine`) por si más adelante se
sustituye un algoritmo por un modelo de ML. Muchas dependen de que exista el core
operativo mínimo (ubicaciones, órdenes), así que se sincronizan con su
construcción.

**Actividades:**

- [ ] Evaluar e incorporar OR-Tools (o solver equivalente) al stack.
- [x] Definir puertos base: `IPickingRouter`, `IBatchGrouper` (+ Fake* y
      factories; hook en `fulfillment/picking/domain/routing.py`).
- [ ] Definir puertos adicionales: `ISlottingEngine`, `ICartonizer`,
      `IDispatchRouter`.
- [ ] **Ruta de picking** (`route-optimization`): secuenciar paradas dentro de la
      bodega minimizando recorrido (requiere modelo de layout).
- [ ] **Agrupación de olas/lotes** (`wave-picking`, `batch-picking`,
      `order-grouping`): agrupar órdenes para minimizar viajes.
- [ ] **Slotting óptimo** (`optimal-slotting`): asignar SKU a ubicaciones por
      rotación/peso/compatibilidad/capacidad.
- [ ] **Cartonización** (`optimal-package-recommendation`): elegir caja/embalaje
      óptimo por dimensiones-peso-costo (bin packing).
- [ ] **Ruteo de despacho** (`route-optimization`, `zone-grouping`): consolidar
      despachos por geografía (VRP).
- [ ] **Asignación de bodega** (`optimal-warehouse`): decidir desde qué bodega
      surtir (multi-warehouse) por costo/tiempo.
- [ ] Ejecutar los cálculos pesados en Celery; exponer resultados vía API.
- [ ] Tests con escenarios conocidos (validar optimalidad esperada).

**Definición de Done de la Fase 2:**

- [ ] Al menos ruta de picking y agrupación de olas operativas y medibles
      (reducción de recorrido demostrable).
- [ ] Los solvers corren en background sin bloquear requests.
