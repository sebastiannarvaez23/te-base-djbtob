# FASE 3 — Suite de tests unitarios

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 2](fase-2-capa-datos.md) · **Fase 3** · Siguiente → [Fase 4](fase-4-admin-web.md)

> **Continuidad — qué se hizo en la Fase 2.** La Fase 2 entregó la feature
> `platform/features/release/feature_flag/`: modelos `FeatureFlag` /
> `FeatureFlagScope` en schema público, repositorio Django, use cases CRUD con
> invalidación `feature_flags:*`, adaptador `CachedDjangoFlagStore` conectado a
> `get_flag_store()`, API admin (`/platform/feature-flags/`), códigos `FLAG_*`,
> `audit_log` en mutaciones y tests unitarios de esa capa. El runtime de
> `core/flags` ya puede evaluar flags reales en caliente. **La Fase 3 no añade
> producto nuevo:** consolida y completa la **suite unitaria** del mecanismo
> extremo a extremo (evaluador + scopes + store + ciclo de vida + resiliencia),
> sin depender aún de un caso de negocio concreto.
>
> **Qué se hizo ya en fases anteriores (no rehacer, sí reutilizar):**
> - Fase 1: tests del núcleo (`core/tests/unit/flags/`) — matchers, evaluador,
>   facade, `FakeFlagStore`.
> - Fase 2: tests de use cases, invalidación de caché y adaptador de store
>   (`platform/tests/unit/release/`).
>
> **Qué queda como punto de partida de esta fase:**
> - Cerrar huecos de cobertura (matriz status × enabled × scopes × contexto).
> - Casos de resiliencia (Redis caído, repo que falla, contexto parcial).
> - Extensibilidad (registrar un `ScopeType` de prueba sin tocar el evaluador).
> - Contrato de defaults (`FlagKeys` sin fila en BD → lógica antigua).
> - Auth de API admin (request mockeado) si aún no está cubierto.
>
> **Qué queda explícitamente fuera de esta fase:** UI en `base-admin-web` (Fase 4)
> y el primer caso de negocio real (pendiente fuera de este plan).

**Objetivo:** dejar una suite unitaria que valide de forma exhaustiva el
comportamiento del sistema de release flags, de modo que cualquier feature
futura pueda confiar en `is_enabled` sin redescubrir reglas.

**Descripción detallada:** Aunque las Fases 1 y 2 ya aportan tests, esta fase
trata la calidad del mecanismo como entregable propio: matriz de evaluación,
fallos de infraestructura, ciclo de vida y extensibilidad de scopes. No se
requiere un dominio de warehouse concreto; se usan stores fake/mocks y
definiciones en memoria o fixtures mínimas.

**Actividades:**

- [x] Matriz de evaluación (tabla de casos):
      - Cada `FlagStatus` × `enabled` True/False.
      - Sin scopes (global) vs con scopes.
      - Match y no-match para `COMPANY`, `USER`, `COUNTRY`, `STATE`, `CITY`.
      - OR entre varios scopes (basta uno para activar).
- [x] Contexto parcial: sin `company_id`, sin `user_id`, sin campos de
      ubicación → no match en scopes que los requieren; global sigue OK.
- [x] Resiliencia:
      - `IFlagStore` que lanza excepción → `False`.
      - Lectura de caché que falla → degradación a lógica antigua (o recarga
        controlada documentada en el adaptador; el request no rompe).
      - Key ausente en store → `False`.
- [x] Extensibilidad: test que registra un matcher de un `ScopeType` de prueba y
      verifica que el evaluador lo usa sin cambios de código en
      `FlagEvaluator`.
- [x] Defaults: constante en `FlagKeys` sin definición persistida → `False`.
- [x] Ciclo de vida: `CERTIFIED`, `ARCHIVED`, `DRAFT`, `DISABLED` nunca
      devuelven `True` aunque `enabled=True` y haya scopes.
- [x] API admin (unitario con mocks): rechazo sin auth admin; create/update
      validan key única y `scope_type` válido.
- [x] Documentar en el resumen teórico o docstring cómo ejecutar la suite:
      `pytest core/tests/unit/flags/ platform/tests/unit/release/`.

**Definición de Done de la Fase 3:**

- [x] La matriz de casos anterior está cubierta por tests unitarios en verde.
- [x] Ningún test de evaluación depende de un caso de negocio de warehouse.
- [x] Un fallo simulado de infra en evaluación no propaga excepción al caller.
- [x] Queda documentado cómo correr la suite del mecanismo de flags.

### Archivos añadidos en esta fase

| Archivo | Rol |
|---------|-----|
| `core/tests/unit/flags/test_evaluation_matrix.py` | Matriz status×enabled, scopes, contexto parcial, resiliencia, FlagKeys |
| `platform/tests/unit/release/test_feature_flag_api.py` | Auth admin, validación key/scope, create/list, duplicate key → 409 |
| `platform/tests/unit/release/test_flag_store_resilience.py` | Caché hit/miss, Redis caído, fallback a repo / legacy |
