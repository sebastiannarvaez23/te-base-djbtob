# FASE 0 — Cimientos técnicos (`core/ai/`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 0** · Siguiente → [Fase 0b](fase-0b-runtime-slm.md)

> **Continuidad — punto de partida.** Es la **primera fase de construcción**, así
> que no hay fase anterior que resumir. Su único prerequisito es el
> [resumen teórico](00-resumen-teorico.md): la arquitectura de puertos/adaptadores
> (`core/ai/` como gemelo de `core/storage/`), los 4 cubos de IA y la restricción
> del arranque en frío. La Fase 0 monta la "tubería" transversal que **todas**
> las fases siguientes consumen. El **runtime SLM nativo** y el kill-switch de
> infra se abordan en la [Fase 0b](fase-0b-runtime-slm.md) (decisión 2026-07-31:
> el chat no depende de proveedor gestionado).

**Objetivo:** construir la "tubería" transversal de IA (puertos, adaptadores,
observabilidad, config) sin construir todavía ninguna feature de negocio. Al
terminar, cualquier feature podrá consumir IA con inyección de dependencias, y
cambiar de backend de inferencia será trivial.

**Descripción detallada:** Es el equivalente para IA de lo que `core/storage/` es
para el almacenamiento de objetos. Definimos el contrato abstracto (`IChatModel`,
`IEmbedder`, `IDocumentExtractor`), implementamos adaptadores de referencia
(`fake` obligatorio; `anthropic` opcional) y las capacidades que la IA necesita:
observabilidad, caché/idempotencia, timeout+fallback y redacción de PII. El
adaptador **local → SLM** es el siguiente paso (Fase 0b).

**Actividades:**

- [x] Decidir el proveedor gestionado de *referencia* (Anthropic/Claude como
      adaptador opcional; `fake` como default seguro).
- [ ] Validar el contrato de **zero-data-retention** apto para B2B **solo si** se
      activa un adaptador gestionado en algún entorno (no bloquea el chat SLM).
- [ ] Fijar la versión del SDK `anthropic` en `requiriments.txt` (dejada como
      dependencia OPCIONAL comentada; descomentar solo al activar ese adaptador).
- [x] Crear `core/ai/domain/genai/schemas.py` (re-export en `domain/schemas.py`)
      con los contratos Pydantic: `Message`, `Prompt`, `Completion`, `TokenUsage`,
      `EmbeddingResult`, `ExtractionResult`.
- [x] Crear `core/ai/domain/genai/interfaces.py` (re-export en `domain/interfaces.py`)
      con los puertos: `IChatModel` (`complete()` / `stream()`), `IEmbedder`
      (`embed()`), `IDocumentExtractor` (`extract()`).
- [x] Implementar adaptadores en `core/ai/infrastructure/genai/`
      (`anthropic_provider.py` opcional; `fake_provider.py` para
      `IChatModel`, `IEmbedder` y `IDocumentExtractor`).
- [x] Particionar `core/ai` por capacidad (`genai` / `optimization` / `predictive`)
      con factories y Fake* por familia.
- [x] Implementar `core/ai/config.py`: selección de proveedor/modelo vía
      `settings` y variables `.env` (django-environ), con posibilidad futura de
      override por tenant (`AI_ENABLED`, `AI_PROVIDER`, …).
- [x] Implementar `core/ai/observability/usage_tracker.py`: registro de tokens
      de entrada/salida, costo estimado (si aplica), latencia, modelo y
      `tenant_id` por llamada.
- [x] Implementar `core/ai/observability/cache.py`: caché/idempotencia de prompts
      (reutilizar Redis del stack).
- [x] Implementar timeout + fallback (degradación best-effort): `resilience.py`
      (`complete_or`) + timeout en el adaptador; si el backend de inferencia
      falla/tarda, devuelve un resultado degradado y registra el fallo.
- [x] Añadir familia de errores `AI_00x` en `core/errors/codes.py`
      (timeout, proveedor/runtime no disponible, cuota excedida, respuesta
      inválida).
- [x] Integrar la **redacción de PII** (`core/logging_redaction.py`) en la
      construcción de prompts (`safety.py`).
- [x] Documentar en el `CLAUDE.md` de base el nuevo módulo `core/ai/` y
      el patrón de uso (puerto por constructor).
- [x] Tests: unit del contrato con un adaptador *fake* (`FakeChatModel`) para que
      las features se puedan testear sin runtime real.

**Definición de Done de la Fase 0:**

- [x] Existe un `FakeChatModel` y un adaptador real de referencia intercambiables
      por config.
- [x] Una llamada de prueba registra correctamente tokens/costo/latencia.
- [x] Una caída simulada del backend de inferencia **no** rompe el request
      (degrada).
- [x] Cambiar de adaptador requiere solo configuración, no código de dominio.
