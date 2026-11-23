# FASE 3 — Capa IA-nativa (assistant / copiloto)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 2](fase-2-optimizacion-or.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-instrumentacion-datos.md)

> **Continuidad — prerequisitos.** La Fase 0 dejó `core/ai/` listo. La
> **[Fase 0b](fase-0b-runtime-slm.md)** dejó el **SLM nativo** (adaptador
> `local` + runtime + kill-switch). La Fase 1 puede aportar features GenAI
> puntuales; la Fase 2 aporta optimizaciones OR invocables como tools. **Esta
> fase** construye el diferenciador de producto: el chat **assistant** en
> `base-client-web`, cableado al backend, con agente estrecho sobre el SLM.
> Sigue sin necesitar datos históricos de ML.

**Objetivo:** que el **assistant** responda en lenguaje natural y opere el
WMS de forma segura mediante *tool-calling* sobre use cases existentes, usando
el **SLM nativo** (no un proveedor en el camino crítico). Si la IA está
inactiva, el chat no debe disparar inferencia ni mantener el runtime encendido
por su cuenta.

**Descripción detallada:** El operador pregunta (*"¿qué órdenes de hoy están en
riesgo?"*, *"estado del pedido ORD-0001"*). El SLM **no toca la BD**:
solicita tools (wrappers de use cases). El backend valida tenant/permisos,
ejecuta y devuelve el resultado; el modelo compone una respuesta **corta**.
Protocolo JSON apto para SLM pequeño (`action=tool|final`). Feature:
`client/features/communication/assistant/chat/`.

**Alcance MVP (hecho):**

1. Chat solo-lectura + historial auditable.
2. Registro de tools whitelist + bucle de agente.
3. REST + **streaming WebSocket** (thinking / tool / token / done).
4. Gates: `AI_ENABLED`; UI muestra desactivado; **sin llamadas al runtime**.

**Fuera del MVP inmediato (pendiente en esta fase):** ver §
[*Pendiente enriquecido — retomar assistant*](#pendiente-enriquecido--retomar-assistant-post-mvp)
(tools facilities/stock, gate duro tool-before-facts, lexicón WMS, NL-BI,
alertas, rule-suggestion).

**Streaming nativo (hecho):** el agente usa ``model.stream()``; un extractor
incremental saca el campo ``text`` del JSON ``action=final`` y lo emite como
``assistant.token`` en vivo (cola hilo→WS). Si no hay stream, se pacea al final.

**Actividades:**

### Backend — agente y dominio

- [x] Registro de herramientas (tools) sobre use cases de pedidos/referencias.
- [x] Bucle de agente JSON (máx. 4 pasos) sobre `IChatModel`.
- [x] Guardrails: whitelist; tools de escritura exigen `confirmed`; sin SQL.
- [x] Aislamiento multi-tenant: historial en schema tenant; API con
      `IsCompanyMember`.
- [x] Persistir historial (`AssistantConversation` / `Message` / `ToolCall`).
- [x] Feature hexagonal `client/features/communication/assistant/chat/`.
- [x] Uso vía `complete_or` + `usage_tracker` (feature=`assistant.chat`).
- [x] Si IA off: `AI_006` y cero llamadas al modelo (tests).

### Tiempo real y UX

- [x] Endpoints REST bajo `api/v1/assistant/` (status, chat, conversations).
- [x] Streaming WebSocket `ws/assistant/` (thinking → tool → typing → token → done).
- [x] Cablear `assistant` en `base-client-web` (WS preferido; fallback REST).
- [x] Si IA off: estado «Desactivado» e input bloqueado.

### Capacidades adicionales (post-MVP) — checklist corto

- [ ] Consulta NL / BI amplia vía más tools → detalle en § *Pendiente enriquecido*.
- [ ] Alertas proactivas explicadas.
- [ ] Sugerencia de reglas (`rule-suggestion`).

### Tests

- [x] Agente no ejecuta tools fuera de whitelist.
- [x] Escrituras requieren confirmación (registry).
- [x] `AI_ENABLED=False` → 0 llamadas al modelo.
- [x] Bucle con modelo scripted / `FakeChatModel` en CI.
- [ ] Test de integración API + no-cross-tenant (ampliar cuando haya fixture
      multi-tenant del chat).
- [ ] Tests del gate duro `require_tool_before_facts` (ver backlog A2).
- [ ] Tests de cada tool nueva (handler + registro + status map).

**Definición de Done de la Fase 3 (MVP chat):**

- [x] assistant responde (MVP) vía tools de solo-lectura + SLM/`fake`.
- [x] Ninguna acción destructiva sin confirmación (MVP: solo tools read-only).
- [x] Auditoría de tools en `assistant_tool_calls`.
- [x] Con IA off, no hay inferencia (gate en use case + UI).

**Ops:** tras deploy, `python manage.py migrate_schemas` para crear tablas del
app `assistant` en schemas tenant.

---

## Pendiente enriquecido — retomar assistant (post-MVP)

> **Estado al documentar:** 2026-09-25.  
> **Síntoma observado (chat real exportado):** preguntas del tipo *«¿Cómo
> están las bodegas?»*, *«¿cuántas bodegas tenemos operando?»*, *«relación
> bodegas ↔ indicadores»* producen respuestas incorrectas: habla de
> *bibliotecas*, aconseja en prosa usar `list_orders` /
> `get_order_indicators`, o afirma datos sin haber consultado facilities.  
> El prototipo UX `/status` (secuencia de fases en el indicador) **sí**
> funciona; el fallo es de **cobertura de tools + guardrails + protocolo
> SLM**, no del indicador de proceso.

### Cómo funciona hoy (recordatorio para retomar)

```
UI (WS/REST) → ChatTurn(Stream)UseCase
  → load_chat_runtime()  # policy plataforma + build_default_tool_registry
  → get_chat_model()     # fake | local | anthropic
  → AssistantAgent.iter_events()  # ≤ max_agent_steps
       1. Prompt(system JSON protocol + catálogo tools + UI context)
       2. stream_accumulate_or(model) → texto libre
       3. parse_agent_action() → action=tool|final
       4. tool → registry.execute → reinyecta "Tool result…"
       5. final → tokens al cliente + auditoría
```

- **El modelo nunca toca la BD.** Solo pide tools; los handlers llaman use
  cases existentes y devuelven JSON compacto.
- **Protocolo:** JSON *prompted* (`{"action":"tool","name":…}` /
  `{"action":"final","text":…}`), **no** function-calling nativo del
  runtime. El SLM pequeño (`qwen2.5:1.5b`) es frágil: inventa nombres,
  traduce mal el dominio o escribe tools en prosa.
- **`require_tool_before_facts`:** hoy es **solo prompt**. No hay rechazo
  en código de un `action=final` sin tool exitosa en el turno.

### Inventario actual de tools (MVP)

| Tool | Use case | Archivo handler |
|------|----------|-----------------|
| `get_order_by_number` | `GetOrderByNumberUseCase` | `…/assistant/chat/infrastructure/tools.py` |
| `list_orders` | `ListOrdersUseCase` | idem |
| `get_order_indicators` | `GetOrderIndicatorsUseCase` | idem |
| `list_references` | `ListReferencesUseCase` | idem |
| `get_reference` | `GetReferenceUseCase` | idem |

Catálogo canónico: `core/ai/assistant_catalog.py` → `ASSISTANT_TOOL_KEYS`.  
Mapa tool → status UI: `core/ai/assistant_status.py` → `_TOOL_STATUS_MAP`.  
Toggles admin: `platform/features/configuration/assistant/`.  
Agente / prompt: `…/assistant/chat/application/agent.py`.

**No cableado aún:** facilities/bodegas, balances/stock, ubicaciones, picking,
receiving, OR/ML. Por eso *«cuántas bodegas operando»* no puede contestarse
bien aunque el use case WMS ya exista.

### Diagnóstico de las fallas del chat de ejemplo

| Síntoma | Causa raíz | Qué no arregla solo |
|---------|------------|---------------------|
| Habla de *bibliotecas* | SLM libre / glosario ausente; término WMS = bodega/warehouse/facility | Reintentar con el mismo catálogo |
| Menciona `list_orders` / `get_order_indicators` en prosa | Modelo no emite JSON `action=tool`; “explica” el catálogo | Más pasos del bucle sin gate |
| No cuenta bodegas operativas | **No hay tool** sobre facilities | Prompt más largo |
| Datos inventados o “no hay órdenes…” ante pregunta de bodega | Soft `require_tool_before_facts` + Fake enruta *bodega* → `list_orders` | Solo cambiar el modelo |

Use case ya disponible para el primer gap (sin tool aún):

- `ManageFacilitiesUseCase.list_warehouses(page, page_size, filters)`  
  en `client/features/warehouse/site/facilities/`  
  (filtro típico: `status=ACTIVE` → `{total, items[{id,code,name,status}]}`).

---

### Backlog priorizado (retomable)

#### A1 — Ampliar whitelist: facilities / bodegas *(P0 — desbloquea el chat de ejemplo)*

- [x] Tool `list_warehouses` en `tools.py`:
  - Handler: `ManageFacilitiesUseCase(DjangoFacilityRepository()).list_warehouses(…)`
  - Args: `status`, `q`, `limit` (≤50).
  - Salida compacta: `{total, items:[{id, code, name, status}]}` vía `_compact`.
- [x] Registrar en `ASSISTANT_TOOL_KEYS` (`assistant_catalog.py`).
- [x] Mapear status UI `searching_warehouses` + i18n en `wa.assistant.phase.*`.
- [x] Few-shot en system prompt del agent para bodegas operativas.
- [x] Heurística `FakeChatModel`: *bodega / almacén / warehouse / facility* →
      `list_warehouses`.
- [x] Evals harness: fake routing + catálogo/status (`run_ai_evals`).
- [ ] Admin: verificar UI de tools al ampliar `ASSISTANT_TOOL_KEYS`.

**DoD A1:** pregunta *«¿cuántas bodegas tenemos operando?»* con
`AI_PROVIDER=local` (o fake con heurística) → tool OK → respuesta con
`total` real del tenant; sin tool → no afirma un número.

#### A2 — Gate duro `require_tool_before_facts` *(P0 — corta alucinaciones)*

- [ ] En `AssistantAgent`, si la policy exige tool-before-facts **y** el
      turno no es orientation **y** no hubo tool exitosa: no aceptar
      `action=final` con hechos de warehouse; forzar texto
      `out_of_scope` (o un único reintento de corrección, luego out-of-scope).
- [ ] Auditar el rechazo (código tipo `FACTS_WITHOUT_TOOL`) para ops.
- [ ] Tests: modelo scripted que hace `final` sin tool → out-of-scope;
      modelo que hace tool OK + final → pasa.

**DoD A2:** imposible que el usuario vea cifras/hechos de bodega/pedido
inventados sin audit de tool `ok` en ese turno (salvo orientation).

#### A3 — Lexicón / prompt WMS *(P1 — calidad de lenguaje)*

- [ ] Bloque fijo en `_SYSTEM_TEMPLATE` (`agent.py`):
  - bodega = warehouse / facility; nunca *biblioteca* / *library*.
  - pedido = order; referencia/SKU = catalog reference.
  - Prohibido inventar nombres de tools; solo whitelist.
- [ ] Few-shots ES/EN cortos para bodegas, pedidos e “out of scope”.
- [ ] Revisar `ASSISTANT_DEFAULT_OUT_OF_SCOPE` (EN) vs copy ES en i18n /
      policy plataforma si el operador ve inglés crudo.

**DoD A3:** en muestras con SLM local, deja de aparecer *biblioteca* en
respuestas de dominio WMS.

#### A4 — Robustez del protocolo tool-calling con SLM pequeño *(P1)*

- [ ] Evaluar: más few-shots; o modelo un poco mayor en ops
      (documentar trade-off CPU en `fase-0b`); o parseo tolerante
      (extraer primer JSON válido / reparación mínima).
- [ ] Si el modelo nombra una tool inventada → ya hay `TOOL_NOT_ALLOWED`;
      asegurar que el siguiente paso no derive en `final` inventado (acoplar A2).
- [ ] Métricas/logs: ratio tool-parse-fail vs tool-ok por turno (`app.ai` /
      auditorías).

**DoD A4:** en suite de prompts golden (bodegas, ORD-xxxx, SKU, orientación
UI), ≥ umbral acordado de tool-calls válidas con el modelo default.

#### A5 — Siguiente oleada de tools NL / BI *(P2 — checklist “consulta amplia”)*

Misma receta que A1 (wrapper read-only → catalog → status → fake → tests).
Prioridad sugerida según valor operativo:

| Prioridad | Tool tentativo | Use case / zona |
|-----------|----------------|-----------------|
| 1 | `list_warehouses` | facilities (A1) |
| 2 | `get_warehouse` / detalle facility | facilities |
| 3 | `list_stock_balances` / por SKU+bodega | `warehouse/inventory/balances` |
| 4 | `list_locations` / zonas | site / layout |
| 5 | `list_pickings` / estado ola | fulfillment/picking |
| 6 | KPIs operativos agregados (si existe use case; si no, **no** inventar SQL) | dashboard / indicators |

- [ ] Mantener **solo lectura** hasta cablear confirmación agentic (`/agent`
      UI ya prototipada; backend write + `confirmed` pendiente de producto).
- [ ] Nunca SQL crudo ni ORM desde el prompt; solo use cases.

**DoD A5 (parcial por tool):** cada tool nueva tiene handler, key, status,
tests y ejemplo en prompt; pregunta golden correspondiente verde en CI fake.

#### A6 — Capacidades producto posteriores *(P3)*

- [ ] Alertas proactivas explicadas (push / digest; no solo Q&A).
- [ ] `rule-suggestion` (propuesta de reglas; ejecución con confirmación).
- [ ] Test integración API chat + aislamiento cross-tenant.
- [ ] Escrituras vía tools con `confirmed` (alinear con tarjeta `/agent` del FE).

---

### Receta: añadir una tool (checklist de implementación)

1. Confirmar use case L4 existente (CA) y que sea **read-only** o tenga
   confirmación.
2. Handler compacto en `infrastructure/tools.py` + `ToolSpec` en
   `build_default_tool_registry`.
3. Añadir key a `ASSISTANT_TOOL_KEYS` (rompe bodies admin a propósito —
   actualizar fixtures/tests de settings).
4. `_TOOL_STATUS_MAP` + i18n FE (`wa.assistant.phase.*`) + lista demo
   `/status` si hay código nuevo.
5. Descripción + ejemplo en system prompt del agente.
6. Heurística en `FakeChatModel` para CI.
7. Tests unitarios agent/tools/status/settings.
8. Probar a mano con `AI_PROVIDER=local` + runtime profile `ai` arriba.

### Runtime / entorno al validar

| Variable / pieza | Esperado para NL real |
|------------------|------------------------|
| `AI_ENABLED` | `True` |
| `AI_PROVIDER` | `local` (no `fake` para composición ES real) |
| Compose profile `ai` / Ollama | proceso arriba; kill-switch respeta “IA off” |
| Policy plataforma | tools habilitadas; `require_tool_before_facts=True` |

Con `fake`, solo se valida el cableado de tools/heurísticas, no la calidad
del español del SLM.

### Criterio de “listo para retomar mañana”

Arrancar por **A1 + A2** juntos: sin tool de bodegas el chat de ejemplo
sigue roto; sin gate duro, un SLM frágil seguirá inventando tras
`TOOL_NOT_ALLOWED`. A3/A4 en cuanto A1 esté verde. A5 por oleadas. A6
cuando el Q&A read-only sea confiable.

### Referencias rápidas de código

| Qué | Dónde |
|-----|--------|
| Bucle agente + prompt | `client/features/communication/assistant/chat/application/agent.py` |
| Turno REST/WS | `…/application/use_cases.py`, `…/realtime/consumer.py` |
| Registry tools | `…/infrastructure/tools.py`, `…/domain/tool_registry.py` |
| Catálogo keys | `core/ai/assistant_catalog.py` |
| Status wire | `core/ai/assistant_status.py` |
| Policy / toggles | `core/ai/assistant_policy.py`, `platform/.../configuration/assistant/` |
| Facilities UC | `client/features/warehouse/site/facilities/application/use_cases.py` |
| UX fases / `/status` | `base-client-web/.../assistant.component.ts` |
| Plan runtime SLM | [fase-0b-runtime-slm.md](fase-0b-runtime-slm.md) |
