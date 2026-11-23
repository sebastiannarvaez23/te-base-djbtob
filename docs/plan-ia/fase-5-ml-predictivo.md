# FASE 5 — ML predictivo

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 4](fase-4-instrumentacion-datos.md) · **Fase 5** · Siguiente → [Fase 6](fase-6-integraciones-ia.md)

> **Continuidad — qué se hizo en la Fase 4.** La Fase 4 dejó instrumentada la
> captura de datos ML-ready: un catálogo de eventos por módulo operativo, marcas
> de tiempo consistentes, **resultados reales (ground truth)** para poder comparar
> contra predicciones, contexto para features, política de retención por tenant y
> una vista/exportación analítica por schema lista para entrenamiento. **Cuando ese
> historial acumula varios meses**, la Fase 5 ya puede entrenar y servir los
> modelos predictivos del cubo 3 sobre esos datos — el único cubo que no era
> viable hasta ahora por falta de historial.

**Objetivo:** entrenar y servir los modelos predictivos del cubo 3, una vez que
exista suficiente historial (típicamente varios meses de operación por tenant).

**Descripción detallada:** Estos modelos se entrenan con los datos capturados en la
Fase 4. Corren **self-hosted, sin GPU** (scikit-learn, XGBoost, Prophet). Se
integran vía puertos (`IDemandForecaster`, `IEtaPredictor`, `IRiskClassifier`),
igual que todo lo demás, de modo que el use case no sepa si detrás hay un modelo
local o, en el futuro, un servicio gestionado. Se empieza por lo más simple y
valioso (típicamente clasificación ABC y predicción de demanda) y se madura el
ciclo MLOps mínimo (entrenar → evaluar → servir → monitorear → reentrenar).

**Actividades (empezar por 1-2 modelos, no todos a la vez):**

- [ ] Confirmar que hay volumen y calidad de datos suficientes (salida de Fase 4).
- [x] Definir puertos base de predicción: `IDemandForecaster`, `IAnomalyDetector`
      (+ Fake*, factories; L3 scaffold `warehouse/intelligence/`).
- [ ] Completar puertos: `IEtaPredictor`, `IRiskClassifier`, `IReorderRecommender`.
- [ ] Montar el pipeline de entrenamiento mínimo (extracción → features →
      entrenamiento → evaluación) — puede orquestarse con Celery/beat.
- [ ] **Clasificación ABC/XYZ** (`abc-classification`) — buen primer modelo
      (simple, alto valor).
- [ ] **Predicción de demanda** (`demand-prediction`) — series temporales.
- [ ] **Predicción de quiebre de stock** (`stockout-prediction`) y
      **recomendación de reorden** (`reorder-recommendation`, combina cubo 3+4).
- [ ] **Predicción de tiempos** (picking/packing/despacho, `*-time-prediction`).
- [ ] **Predicción de ETA de entrega** (`delivery-time-prediction`).
- [ ] **Clasificación de riesgo de orden / crédito** (`risk-classification`,
      `credit-risk-classification`).
- [ ] **Detección de anomalías** (inventario, transacciones, `anomaly-detection`).
- [ ] Servir los modelos vía adaptadores detrás de sus puertos.
- [ ] **Versionado de modelos** y capacidad de rollback.
- [ ] Métricas de calidad del modelo (precisión/error) monitoreadas por tenant.
- [ ] **Detección de drift** y disparador de reentrenamiento.
- [ ] Tests: el use case funciona con un `FakeForecaster`; el modelo real cumple
      umbrales mínimos de calidad antes de promoverse.

**Definición de Done de la Fase 5:**

- [ ] Al menos un modelo (p. ej. ABC o demanda) en producción, versionado y
      monitoreado.
- [ ] Existe un ciclo de reentrenamiento y una política de promoción de modelos.
