# Plan de Trabajo IA — Resumen teórico (base)

> **Propósito de este documento.** Es la hoja de ruta única y compartida para
> incorporar Inteligencia Artificial en la plataforma WMS de forma limpia,
> escalable y mantenible. Está escrito para que **cualquier colega del equipo**
> —incluso sin experiencia previa en IA— entienda qué se va a construir, por qué,
> en qué orden, con qué tecnología y cómo encaja en la arquitectura existente.
>
> **Cómo se usa.** Este archivo contiene la parte **teórica** (contexto, glosario,
> arquitectura, modelos, comunicación, gobernanza y mapa de fases). Cada fase de
> construcción vive en su propio archivo dentro de este mismo directorio
> `docs/plan-ia/`. Cada fase tiene un objetivo, una descripción detallada y una
> lista de actividades con `[ ]` casillas de verificación. Marca `[x]` cuando una
> actividad esté **terminada y verificada** (ver *Definición de Done* de cada fase).
> No marques algo "a medias": si está en progreso, déjalo `[ ]` y anótalo en la
> bitácora al final de este documento.

---

## Índice

### Teoría (este archivo)

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Glosario: los 4 tipos de "IA" (léelo primero)](#2-glosario-los-4-tipos-de-ia-léelo-primero)
3. [Principios de arquitectura](#3-principios-de-arquitectura)
4. [Modelos, SLM nativo y kill-switch](#4-modelos-slm-nativo-y-kill-switch)
5. [Comunicación entre componentes](#5-comunicación-entre-componentes)
6. [Gobernanza de datos y multi-tenancy](#6-gobernanza-de-datos-y-multi-tenancy)
7. [Restricción maestra: el problema del arranque en frío](#7-restricción-maestra-el-problema-del-arranque-en-frío)
8. [Mapa de fases (resumen)](#8-mapa-de-fases-resumen)
9. [Catálogo completo de casos de uso de IA](#9-catálogo-completo-de-casos-de-uso-de-ia)
10. [Bitácora de decisiones](#10-bitácora-de-decisiones)
11. [Harness Engineering (capa de agente)](#11-harness-engineering-capa-de-agente)

### Fases de construcción (un archivo cada una)

- [FASE 0 — Cimientos técnicos (`core/ai/`)](fase-0-cimientos.md)
- [FASE 0b — Runtime SLM nativo (inferencia + kill-switch)](fase-0b-runtime-slm.md)
- [FASE 1 — Primeras features GenAI (sin datos)](fase-1-genai-sin-datos.md)
- [FASE 2 — Optimización operativa (OR)](fase-2-optimizacion-or.md)
- [FASE 3 — Capa IA-nativa (assistant / copiloto)](fase-3-copiloto-agentico.md)
- [FASE 4 — Instrumentación de datos ML-ready](fase-4-instrumentacion-datos.md)
- [FASE 5 — ML predictivo](fase-5-ml-predictivo.md)
- [FASE 6 — Integraciones potenciadas con IA](fase-6-integraciones-ia.md)
- [FASE 7 — Madurez: LLMOps / MLOps](fase-7-llmops-mlops.md)

---

## 1. Contexto y objetivo

**base** es el backend de un WMS (Warehouse Management System) SaaS,
multi-tenant (django-tenants, un schema PostgreSQL por empresa), modelo **B2B**.
El objetivo del negocio es ofrecer a las empresas una plataforma para gestionar
sus operaciones logísticas de forma óptima y sin errores, integrable con SAP,
SIESA, CRMs y otras herramientas.

**Objetivo de este plan:** que la plataforma sea **compatible con IA desde su
núcleo**. No queremos "un WMS con features de IA pegadas", sino una plataforma
donde la IA es un ciudadano de primera clase de la arquitectura, con la
capacidad de:

- Operar el **chat assistant** con un **SLM nativo** (self-hosted), sin
  dependencia de proveedores externos en el camino crítico.
- Mantener la **lógica de IA dentro de `base`** (módulo transversal
  `core/ai/` + features hexagonales), desacoplada del proceso que solo hace
  inferencia.
- **Activar o apagar** la capacidad de chat/IA de forma que, si está inactiva,
  **no consuma recursos de infra** (proceso de inferencia detenido).
- Combinar tres mundos: **IA generativa (SLM/LLM)**, **ML predictivo** y
  **optimización matemática (OR)**.
- Conservar adaptadores a proveedores gestionados como **opción secundaria**
  (features puntuales o fallback futuro), no como camino del copiloto.

**No-objetivos (lo que este plan NO hace):**

- No mete lógica de negocio de IA en los ViewSets/serializers (respetamos la
  arquitectura hexagonal existente).
- No crea un segundo producto/repo “AI engine” con tools, permisos o use cases
  WMS: eso vive en el mono.
- No adopta infraestructura de ML pesada (GPUs, clusters) hasta que haya
  justificación real de datos y ROI.
- No envía datos de un tenant al contexto de otro (aislamiento estricto).
- No apunta a un SLM “generalista” al nivel de Claude/GPT: el chat es **estrecho**
  (intención → tools → respuesta corta).

---

## 2. Glosario: los 4 tipos de "IA" (léelo primero)

> Esta es la sección más importante para quien viene del mundo del software puro.
> **"IA" no es una sola cosa.** En este plan usamos 4 categorías ("cubos") con
> ciclos de vida, infraestructura y habilidades muy distintas. Cada caso de uso
> del catálogo está etiquetado con su cubo.

| Cubo | Nombre | Qué es | Ejemplo en el WMS | ¿Necesita datos históricos? | ¿Camino preferido aquí? |
|------|--------|--------|-------------------|:---------------------------:|:------------------------:|
| **1** | **GenAI texto** | Un modelo de lenguaje que recibe un *prompt* y devuelve texto. No se entrena en caliente; se le dan instrucciones. | assistant, resumen del día, sugerencia de reglas. | ❌ No | **SLM nativo** (chat); managed opcional |
| **2** | **GenAI documentos / visión** | Un modelo multimodal que "lee" imágenes o PDFs y devuelve datos estructurados. | Extraer datos de facturas/POs, daños en fotos, OCR de lotes. | ❌ No | Evaluar local vs managed según ROI |
| **3** | **ML predictivo** | Un modelo *entrenado con tus datos históricos* para predecir un número o clasificar. Usa scikit-learn, XGBoost, Prophet. | Predicción de demanda, ETA, riesgo de orden, ABC. | ✅ **Sí (meses)** | Self-hosted, sin GPU |
| **4** | **Optimización / OR** | Algoritmos matemáticos (investigación de operaciones), **no modelos entrenados**. Usa OR-Tools, solvers. | Ruta de picking, slotting, olas, cartonización, ruteo. | ❌ No (estado actual) | Self-hosted, sin GPU |

**Reglas mentales rápidas:**

- Si la tarea es *"hablar con el operador / componer respuesta tras tools"* →
  cubo 1 → **SLM nativo + agente en el mono**.
- Si la tarea es *"predecir el futuro a partir del pasado"* → cubo 3 → **necesita
  historial, espera a tener datos**.
- Si la tarea es *"encontrar la mejor combinación/orden/asignación"* → cubo 4 →
  **algoritmia en tu infra, sin modelo de lenguaje**.

**Términos que aparecen en el documento:**

- **Prompt**: las instrucciones + contexto que se le envían al modelo.
- **Token**: la unidad de texto que consume un modelo (≈ ¾ de palabra). En SLM
  nativo no hay factura por token, pero tokens = CPU/RAM/latencia.
- **SLM (Small Language Model)**: modelo de lenguaje pequeño (orden ~1B–3B
  parámetros, cuantizado) apto para CPU, bajo coste de cómputo y mantenimiento.
  Suficiente para intención, tool-calling simple y respuestas cortas de dominio.
- **Runtime de inferencia**: proceso **aparte** de Django (p. ej. Ollama o
  llama.cpp server) que carga los pesos del SLM y expone HTTP. **No** contiene
  lógica WMS.
- **Kill-switch**: capacidad de dejar la IA/chat inactiva en **producto** (flag /
  entitlement) e **infra** (contenedor/proceso detenido → ~0 RAM/CPU de
  inferencia).
- **RAG (Retrieval-Augmented Generation)**: primero *buscas* información
  relevante y luego se la das al modelo como contexto.
- **Embedding**: vector de un texto para búsqueda semántica (ej. `pgvector`).
- **Tool-calling / function-calling**: el modelo "pide" ejecutar una función de
  tu código (un use case) en vez de inventar datos. Base del copiloto.
- **Agente**: modelo que, para un objetivo, encadena tools razonando entre pasos.
- **Puerto / Adaptador**: patrón hexagonal. El *puerto* es el contrato; el
  *adaptador* es la implementación intercambiable (`local`, `fake`, opcional
  `anthropic`, …).
- **LLMOps / MLOps**: operar en producción modelos de lenguaje o ML (evals,
  monitoreo, versionado, coste).
- **Drift**: degradación de un modelo ML porque la realidad cambió.
- **Guardrails**: controles de seguridad sobre salidas y acciones del agente.
- **Alucinación**: el modelo inventa información verosímil pero falsa. Se mitiga
  con tools, contexto corto y guardrails.
- **Cold start**: latencia extra al levantar el runtime tras scale-to-zero
  (aceptable a cambio de coste cero cuando el chat está off).

---

## 3. Principios de arquitectura

La IA se integra **respetando la arquitectura hexagonal/DDD existente**. No
inventamos un patrón nuevo: reutilizamos el mismo que ya usan `core/storage/` y
todas las features.

### 3.1 Lógica en el mono; inferencia fuera del proceso Django

| Pieza | Dónde vive | Responsabilidad |
|-------|------------|-----------------|
| Lógica de IA | **`base`** (`core/ai/` + features) | Prompts, agente, tools, permisos, tenant, historial, flags, auditoría |
| Runtime SLM | **Proceso/contenedor aparte** | Cargar pesos y generar tokens (API HTTP compatible) |

No se crea un segundo repo de negocio. El “engine” es solo cómputo de inferencia.

### 3.2 El módulo transversal `core/ai/`

Se crea un módulo hermano de `core/storage/`, con la misma estructura de capas:

```
core/ai/
├── domain/
│   ├── genai/             # Cubos 1–2: IChatModel, IEmbedder, IDocumentExtractor + schemas
│   ├── optimization/      # Cubo 4: IPickingRouter, IBatchGrouper + schemas
│   ├── predictive/        # Cubo 3: IDemandForecaster, IAnomalyDetector + schemas
│   ├── common/            # AiCapability, artefact refs
│   ├── interfaces.py      # Re-export GenAI (compat)
│   └── schemas.py         # Re-export GenAI (compat)
├── infrastructure/
│   ├── genai/             # fake / local / anthropic chat+embed+extract
│   ├── optimization/      # Fake* OR (OR-Tools adapters later)
│   └── predictive/        # Fake* ML (sklearn/Prophet adapters later)
├── observability/
│   ├── usage_tracker.py   # Tokens | solver_ms | predict_ms + capability + tenant
│   └── cache.py           # Caché/idempotencia de prompts (GenAI)
├── resilience.py          # complete_or / solve_or / predict_or
├── safety.py              # Redacción de PII / secretos (GenAI)
├── assistant_policy.py    # Policy del copiloto
└── config.py              # Factories + AI_ENABLED / OR_ENABLED / ML_ENABLED
```

Chat feature path: `client/features/communication/assistant/chat/` (L2 communication).
Predictive L4 scaffold: `client/features/warehouse/intelligence/{demand_forecast,anomaly_detection}/`.

### 3.3 Regla de oro: el dominio depende del puerto, nunca del runtime

Igual que un use case hoy recibe `IReferenceRepository` por constructor, un use
case de IA recibirá `IChatModel` por constructor. **El use case no sabe si detrás
hay un SLM local, `fake` u otro adaptador.** Cambiar de backend de inferencia =
cambiar adaptador/config, sin tocar dominio ni presentación.

```python
# Ejemplo conceptual (application/use_cases.py de una feature)
class GenerateDaySummaryUseCase:
    def __init__(self, model: IChatModel, repository: IOperationsRepository):
        self.model = model            # puerto de IA (cubo 1)
        self.repository = repository  # puerto de datos, ya existente

    def execute(self, tenant_id: str) -> DaySummarySchema:
        metrics = self.repository.get_today_metrics(tenant_id)
        prompt = build_summary_prompt(metrics)
        completion = self.model.complete(prompt)   # vía puerto → runtime SLM
        return DaySummarySchema(text=completion.text)
```

### 3.4 Lo que `core/ai/` añade y `core/storage/` no necesitaba

La IA es **no-determinista, con coste de cómputo y latencia variable**. Por eso
el puerto de IA añade:

- **Observabilidad**: tokens, latencia, modelo, tenant (y costo si hay proveedor).
- **Caché e idempotencia**: prompts equivalentes no deben saturar el runtime.
- **Timeouts + degradación**: si el runtime está caído o cold-starting, la
  feature **degrada** (best-effort); no rompe el flujo operativo del WMS.
- **Gate `AI_ENABLED` / flags**: si la IA está off, **no se llama** al runtime.

### 3.5 Respeto a las convenciones del proyecto

- Errores vía `core/errors/` con códigos semánticos (familia `AI_00x`).
- Respuestas API envueltas con `wrap_response()`.
- Rutas nuevas bajo `api/v1/` (y `urls_public.py` si son de admin).
- Tareas pesadas → **Celery**.
- Streaming del copiloto → **Channels/WebSockets** (reutilizar `inbox/realtime`).

---

## 4. Modelos, SLM nativo y kill-switch

**Decisión vigente (ver [Bitácora](#10-bitácora-de-decisiones)):** el **chat base
Assistant** y, por defecto, el GenAI de texto del copiloto usan un **SLM nativo**
servido en un runtime de inferencia aparte. Objetivo: bajo coste de cómputo,
datos que no salen a un LLM de terceros, y capacidad de apagar el consumo de
infra.

| Necesidad | Cubo | Solución preferida | Notas |
|-----------|:----:|--------------------|-------|
| Chat assistant / agente | 1 | **SLM 1B–3B cuantizado (Q4/Q5) en CPU** vía Ollama o llama.cpp | Un modelo compartido; no fine-tune por tenant al inicio |
| Resúmenes / clasificación de texto | 1 | Mismo runtime SLM (o `fake` en tests) | Contextos cortos |
| Lectura de documentos / visión | 2 | Diferir; evaluar OCR + SLM multimodal o managed puntual | No bloquea el chat |
| Embeddings / RAG | 1 | Modelo de embeddings local + `pgvector` cuando haga falta | Por schema de tenant |
| Predicción (demanda, ETA, riesgo) | 3 | scikit-learn / XGBoost / Prophet — **self-hosted, sin GPU** | Fase 5 |
| Optimización (rutas, slotting) | 4 | OR-Tools — **self-hosted, sin GPU** | Fase 2 |
| Proveedor gestionado (Claude/GPT) | 1/2 | **Opcional / no camino del chat** | Adaptador ya existente; zero-retention si se activa |

### 4.1 Principios de coste (cómputo y mantenimiento)

- **Modelo pequeño y fijo** al inicio; subir tamaño solo con evidencia de uso.
- **Un solo proceso de inferencia** compartido por la plataforma (no un modelo
  por worker Gunicorn ni por tenant).
- **Sin GPU** en el MVP del chat.
- **Sin segundo repo** de lógica: menos contratos y releases que mantener.
- **Sin fine-tune por cliente** al inicio: prompt + tools + datos del schema.
- **Concurrencia acotada** (p. ej. 1–2 inferencias a la vez) + cola si hace falta.

### 4.2 Kill-switch en dos capas (obligatorio)

“Inactivo” debe significar **casi cero recursos de inferencia**, no solo ocultar
el FAB del chat.

| Capa | Mecanismo | Efecto |
|------|-----------|--------|
| **Producto** | `AI_ENABLED` + feature flag / entitlement de plan | UI oculta o 503; use cases no invocan `IChatModel` |
| **Infra** | Compose profile / scale 0 / no arrancar el servicio `ai-runtime` | Contenedor **down** → no RAM/CPU del SLM |

Si solo se apaga producto y el contenedor sigue up, **sigue gastando RAM**. La
Fase 0b define el contrato ops para que off = proceso detenido. Cold start al
volver a encender es un trade-off aceptado.

### 4.3 Configuración

- Selección de adaptador y modelo vía settings / `.env` (`AI_PROVIDER=local|fake`,
  URL del runtime, nombre del modelo).
- Override por tenant a futuro (enterprise “IA off” o cuota).
- Default seguro en desarrollo: `fake` o runtime no arrancado (profile `ai`
  opcional).

---

## 5. Comunicación entre componentes

```
base-client-web (assistant)
        │  HTTP / WebSocket
        ▼
base  ── lógica: agente, tools, permisos, tenant, historial
        │  HTTP (solo si AI on y runtime up)
        ▼
ai-runtime (Ollama / llama.cpp)  ── solo tokens
```

- **Presentación → Aplicación → Puerto de IA.** Igual que el resto del mono: el
  ViewSet no habla con el runtime; el use case recibe `IChatModel`.
- **Síncrono vs asíncrono:** respuestas cortas → HTTP con timeout; lotes /
  documentos → Celery.
- **Streaming del copiloto:** token a token vía Channels cuando el adaptador
  local soporte stream.
- **El modelo nunca toca la BD.** Solo solicita tools; el backend valida
  tenant/permisos, ejecuta el use case y devuelve el resultado al bucle del
  agente.
- **Si IA off o runtime down:** no se abre conexión al runtime; respuesta
  degradada o error de negocio controlado (`AI_*`).
- **Trazabilidad:** `X-Request-ID` + registro de uso (tokens/latencia/modelo).

---

## 6. Gobernanza de datos y multi-tenancy

Con SLM nativo el prompt **no sale a un proveedor** en el camino del chat; igual
aplican reglas fuertes:

- **Aislamiento por tenant.** Contexto solo del schema activo.
- **Redacción de PII** en prompts (`safety.py` / patrón de
  `core/logging_redaction.py`) — útil en logs y si algún día se usa un adaptador
  externo.
- **Un modelo compartido; datos no.** Los pesos son globales; el contexto es por
  request/tenant.
- **RAG / embeddings por schema** cuando existan (nunca índice compartido entre
  empresas).
- **Auditoría** de tools invocadas y metadatos de llamadas al modelo.
- **Consentimiento / plan:** chat activable por feature-flag y entitlement; el
  kill-switch de infra es global u orquestado por ops según política.

Si se activa un adaptador gestionado para otra feature: contratos
**zero-data-retention** B2B y las mismas reglas de redacción/aislamiento.

---

## 7. Restricción maestra: el problema del arranque en frío

> **El WMS operativo aún acumula poco historial.** El ML predictivo (cubo 3)
> **no existe sin datos**.

Consecuencia sobre el orden de trabajo:

- **Se puede hacer ya** (sin historial): cubos **1, 2 y 4** → SLM + copiloto +
  documentos (según madurez) + optimización OR.
- **Debe esperar**: cubo **3** → predicciones.
- **Inversión rentable en paralelo:** instrumentar captura ML-ready (Fase 4)
  mientras se construye el core operativo.

---

## 8. Mapa de fases (resumen)

| Fase | Nombre | Cubos | ¿Necesita datos? | Depende de |
|:----:|--------|:-----:|:----------------:|-----------|
| **0** | Cimientos técnicos (`core/ai/`) | — | No | — |
| **0b** | Runtime SLM nativo + kill-switch infra | 1 | No | Fase 0 |
| **1** | Primeras features GenAI | 1, 2 | No | Fase 0 (ideal: 0b para texto real) |
| **2** | Optimización operativa (OR) | 4 | No | Core operativo básico |
| **3** | assistant / copiloto agéntico | 1 | No | Fase 0, **0b** |
| **4** | Instrumentación de datos ML-ready | — | Genera datos | **En paralelo, cuanto antes** |
| **5** | ML predictivo | 3 | **Sí** | Fase 4 + meses de datos |
| **6** | Integraciones potenciadas con IA | 1 | No | Fase 0 (ideal: 0b) |
| **7** | Madurez: LLMOps / MLOps | todos | — | Transversal, continua |

> **Orden:** la Fase 0 está en gran parte hecha. La **0b** desbloquea el chat
> nativo y el apagado real de cómputo. La Fase 3 es el foco del assistant.
> Fases 1, 2 y 6 pueden avanzar en paralelo tras 0/0b. Fase 4 temprano; Fase 7
> desde que haya algo en producción.

---

## 9. Catálogo completo de casos de uso de IA

Consolidación de necesidades de IA del WMS, por cubo y fase. (Fuente ampliada de
[features-catalog-pending.md](../features-catalog-pending.md)).

### Inbound (entrada)

- [ ] Cita de muelle / dock scheduling — Cubo 4+3 — Fase 2/5
- [ ] Lectura de documentos de entrada (facturas, POs, packing lists) — Cubo 2 — Fase 1
- [ ] Conciliación PO vs recibido — Cubo 1/3 — Fase 1/5
- [ ] Predicción de volumen de recepción — Cubo 3 — Fase 5
- [ ] Control de calidad visual (daños, etiquetas) — Cubo 2 — Fase 1+
- [ ] Sugerencia de ubicación (putaway) — Cubo 4 — Fase 2
- [ ] Clasificación automática de SKU nuevo — Cubo 1 — Fase 1

### Almacenamiento e inventario

- [ ] Slotting óptimo — Cubo 4 — Fase 2
- [ ] Clasificación ABC/XYZ — Cubo 3 — Fase 5
- [ ] Predicción de quiebre de stock — Cubo 3 — Fase 5
- [ ] Recomendación de reorden / safety stock dinámico — Cubo 3+4 — Fase 5
- [ ] Detección de obsoletos / slow-movers — Cubo 3 — Fase 5
- [ ] Optimización de conteos cíclicos — Cubo 3 — Fase 5
- [ ] Detección de anomalías de inventario — Cubo 3 — Fase 5
- [ ] Predicción de ocupación de bodega — Cubo 3 — Fase 5

### Outbound (salida)

- [ ] Predicción de prioridad / riesgo de orden — Cubo 3 — Fase 5
- [ ] Asignación óptima de bodega (multi-warehouse) — Cubo 4 — Fase 2
- [ ] Agrupación de picking (batch/wave) — Cubo 4 — Fase 2
- [ ] Optimización de ruta de picking — Cubo 4 — Fase 2
- [ ] Asignación inteligente de tareas — Cubo 4+3 — Fase 2/5
- [ ] Cartonización / recomendación de empaque — Cubo 4 — Fase 2
- [ ] Predicción de tiempo de picking/packing/despacho — Cubo 3 — Fase 5
- [ ] Detección de error en picking — Cubo 2/3 — Fase 1+/5
- [ ] Selección óptima de transportista — Cubo 3+4 — Fase 2/5
- [ ] Predicción de tiempo de entrega (ETA) — Cubo 3 — Fase 5
- [ ] Agrupación por zona / ruteo de despacho (VRP) — Cubo 4 — Fase 2
- [ ] Predicción de envíos fallidos — Cubo 3 — Fase 5

### Transversales

- [ ] Gestión inteligente de devoluciones (disposición) — Cubo 1/3 — Fase 1/5
- [ ] Pronóstico de fuerza laboral / detección de cuellos de botella — Cubo 3 — Fase 5
- [ ] Visión: conteo de pallets, dimensionamiento, OCR de lotes/series — Cubo 2 — Fase 1+
- [ ] Detección de fraude / anomalías operativas — Cubo 3 — Fase 5
- [ ] Trazabilidad inteligente (consulta NL sobre grafo de movimientos) — Cubo 1 — Fase 3

### Capa IA-nativa (assistant)

- [x] Copiloto conversacional / agente (tool-calling) sobre SLM nativo — Cubo 1 — Fase 3 *(MVP chat + 5 tools orders/refs; ver backlog post-MVP en [fase-3](fase-3-copiloto-agentico.md#pendiente-enriquecido--retomar-assistant-post-mvp))*
- [x] BI / consulta en lenguaje natural (vía más tools, nunca SQL crudo) — Cubo 1 — Fase 3 *(P0 parcial: `list_warehouses` + gate tool-before-facts; más tools pending)*
- [ ] Resumen operativo inteligente (smart-day-summary) — Cubo 1 — Fase 1
- [ ] Alertas proactivas explicadas — Cubo 1 — Fase 3
- [ ] Motor de automatización asistido (rule-suggestion) — Cubo 1/3 — Fase 3

### Integraciones

- [ ] Mapeo de esquemas asistido por modelo — Cubo 1 — Fase 6
- [ ] Normalización de datos maestros — Cubo 1/3 — Fase 6
- [ ] Conciliación inteligente WMS ↔ ERP — Cubo 3 — Fase 6

---

## 10. Bitácora de decisiones

Registro cronológico de decisiones estratégicas de IA (append-only).

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-07-01 | Empezar con proveedor gestionado (no self-hosted). | Cero infra de ML; arranque rápido; puertos permiten migrar después. |
| 2026-07-01 | Arquitectura por puertos/adaptadores en `core/ai/`, hermano de `core/storage/`. | Hexagonal existente; desacopla dominio del backend de inferencia. |
| 2026-07-01 | Priorizar cubos 1, 2 y 4 sobre el cubo 3. | Poco historial operativo; ML predictivo no viable aún. |
| 2026-07-01 | Instrumentación de datos (Fase 4) en paralelo cuanto antes. | Capturar ML-ready ahora es barato; retrofitearlo después es caro. |
| 2026-07-31 | **Pivot: chat assistant = SLM nativo por defecto** (no proveedor en el camino crítico). | Coste de cómputo controlable, datos no salen a LLM de terceros, alineado a B2B. |
| 2026-07-31 | **Lógica de IA permanece en `base`**; solo el runtime de inferencia es proceso aparte. | Evitar segundo repo de negocio; reutilizar auth, tenant, tools y use cases. |
| 2026-07-31 | **Kill-switch en dos capas** (producto + infra scale-to-zero). | “Inactivo” debe liberar RAM/CPU del modelo, no solo ocultar UI. |
| 2026-07-31 | MVP de chat: **SLM ~1B–3B en CPU**, contexto corto, tools whitelist, sin GPU ni fine-tune por tenant. | Máximo valor / mínimo mantenimiento y coste. |
| 2026-07-31 | Adaptadores gestionados (`anthropic`, etc.) quedan **opcionales**, no requisito del copiloto. | La Fase 0 ya los dejó listos; no bloquean ni definen el chat. |
| 2026-07-31 | Runtime MVP = **Ollama**; modelo inicial = **`qwen2.5:1.5b`**; compose profile **`ai`**. | API OpenAI-compatible, pull simple, profile = kill-switch de infra sin tocar el stack base. |
| 2026-09-25 | Post-MVP assistant: ampliar tools (empezar por **facilities/`list_warehouses`**) + **enforce en código** de `require_tool_before_facts`; prompt/lexicón WMS. Detalle en fase-3 § pendiente enriquecido. | Chat real fallaba en preguntas de bodegas (alucinación / tools en prosa / sin wrapper de facilities); el bucle MVP existe pero el catálogo orders+refs no cubre el dominio. |
| 2026-10-18 | **Harness Engineering** en `core/ai/harness/` (Agent Loop, cancel Redis, HookBus, CapabilityBoundary, gate tool-before-facts, `AgentRun`). | Estandarizar AI Engineering sin segundo repo; lógica modular y testeable. |
| 2026-10-18 | **BYOK self-service** en `base-client-web` (keys cifradas vía `ISecretStore`); platform no ve la key. | Flexibilidad Claude/OpenAI del cliente sin mezclar secretos en admin. |
| 2026-10-18 | **Control plane IA completo** en `/admin/ia` desde el inicio (tabs stub incluidos). | Gestión alcanzable de todas las capacidades aunque el runtime aún no esté cableado. |

> Añade aquí toda decisión futura (cambio de runtime, tamaño de modelo, GPU,
> fine-tune, política de datos, etc.) con fecha y motivo.

---

## 11. Harness Engineering (capa de agente)

Mapa de conceptos → código (implementación incremental; H1+ en curso):

| Concepto | Ubicación |
|----------|-----------|
| Agent Loop | `core/ai/harness` + `AssistantAgent` |
| Capa de modelos | `core/ai/config.py` → router/budgets (H2) |
| Contexto | prompt + `ui_context` + history; `ContextPack` (evolución) |
| Sesiones / estado | `AssistantConversation` + **`AssistantAgentRun`** |
| Herramientas | `ToolRegistry` + CapabilityBoundary |
| Entorno | deny-by-default (solo tools whitelist) |
| Interfaz de control | WS `assistant.cancel` / `assistant.cancelled`; admin Runs (H3) |
| Extensiones | `HookBus` (`before_run` … `on_final`) |

**Restricciones técnicas (obligatorias):** CA solo en L4; SOLID; Pydantic en contratos; uuid7; `@validated_body` / `@validated_query`; mensajes EN en envelopes; listas paginadas; errores `core/errors`; Redis en hot paths (cancel/budgets); ACID en mutaciones de inventario/cobros vía tools; cobertura unitaria del código nuevo; lógica modular y económica en cómputo.
