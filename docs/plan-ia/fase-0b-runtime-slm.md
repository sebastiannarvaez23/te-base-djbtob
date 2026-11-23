# FASE 0b — Runtime SLM nativo (inferencia + kill-switch)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 0](fase-0-cimientos.md) · **Fase 0b** · Siguiente → [Fase 1](fase-1-genai-sin-datos.md)

> **Continuidad — qué se hizo en la Fase 0.** La Fase 0 montó `core/ai/`: puertos
> (`IChatModel`, `IEmbedder`, `IDocumentExtractor`), adaptadores `fake` y
> `anthropic` (opcional), `config.py` (`AI_ENABLED`, `AI_PROVIDER`),
> observabilidad, caché, `complete_or`, `safety.py` y errores `AI_*`. **Falta el
> camino nativo del chat:** un adaptador que hable con un proceso de inferencia
> local y la capacidad de **no consumir infra** cuando la IA está apagada. Eso es
> esta fase. No construye aún el assistant (Fase 3); solo la tubería de
> cómputo y el contrato de encendido/apagado.

**Objetivo:** disponer de un **runtime de inferencia SLM** (proceso aparte de
Django), un adaptador `local` detrás de `IChatModel`, y un **kill-switch de
infra** tal que, con IA inactiva, el contenedor/proceso del modelo esté
**detenido** (~0 RAM/CPU de inferencia).

**Descripción detallada:** La lógica de negocio de IA **sigue en `base`**.
El runtime (Ollama) solo carga pesos y genera tokens vía API OpenAI-compatible
(`POST /v1/chat/completions`). Un único servicio compartido sirve a todos los
tenants. En desarrollo el profile `ai` es opcional; cold start al reactivar es
aceptable.

**Actividades:**

### Runtime e imagen

- [x] Elegir runtime MVP: **Ollama** (API OpenAI-compatible; el contenedor escucha en `11434` y el host lo publica en `3310`).
- [x] Fijar modelo inicial: **`qwen2.5:1.5b`** (familia ~1–2B, apto CPU).
- [x] Añadir servicio `ai-runtime` a `docker-compose` bajo **profile `ai`**.
- [x] Healthcheck del runtime (`ollama list`) y `mem_limit` (default 4g).
- [x] Documentar en README: encender (`--profile ai`), pull del modelo, apagar,
      smoke test.

### Adaptador en `core/ai/`

- [x] Implementar `core/ai/infrastructure/local_provider.py` (`complete` +
      `stream` SSE).
- [x] Extender settings: `AI_PROVIDER=local`, `AI_RUNTIME_URL`, `AI_CHAT_MODEL`,
      `AI_MAX_CONCURRENT`, timeouts/tokens.
- [x] Si `AI_ENABLED=False`: `get_chat_model()` (no-fake) lanza `AI_006`; runtime
      unreachable → `AI_001` sin reintentos agresivos.
- [x] Tests unit del adaptador local con HTTP mock (CI sin modelo real).
- [x] Smoke test manual documentado en README (`manage.py shell` +
      `get_chat_model('local')`).

### Kill-switch (producto + infra)

- [x] Producto off: `AI_ENABLED=False` → no se instancia adaptador `local`
      (excepción `AI_DISABLED`).
- [x] Infra off: compose **sin** profile `ai` → no corre `ai-runtime`.
- [x] Contrato documentado: profile down = sin proceso del modelo.
- [x] Runbook breve en README (activar: profile + env + pull).

### Coste y operación

- [x] Footprint documentado en README (~2–3 GB con modelo cargado; cold start).
- [x] `AI_MAX_CONCURRENT` (default 1) en settings + semáforo en el adaptador.
- [x] **Sin GPU** en MVP (bitácora 2026-07-31).

**Definición de Done de la Fase 0b:**

- [x] Con profile `ai` up y `AI_PROVIDER=local`, un `complete()` habla con el
      runtime vía `IChatModel` (smoke manual + adaptador listo).
- [x] Con profile `ai` down (o IA off), **no** hay contenedor de inferencia por
      defecto / factory bloquea `local`.
- [x] CI pasa sin runtime real (mocks / `fake`) — `pytest core/tests/unit/ai/`.
- [x] Cambiar de modelo en el runtime = solo config (`AI_CHAT_MODEL` / pull).
