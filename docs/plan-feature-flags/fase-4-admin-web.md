# FASE 4 — Pantalla administrativa (`base-admin-web`)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · ← [Fase 3](fase-3-tests.md) · **Fase 4**

> **Continuidad — qué se hizo en la Fase 3.** La Fase 3 consolidó la suite
> unitaria del mecanismo: matriz status × enabled × scopes × contexto,
> resiliencia ante fallos de store/caché, extensibilidad de matchers, defaults
> de keys desconocidas, ciclo de vida (`CERTIFIED` / `ARCHIVED` / etc. no
> evalúan ON) y cobertura de auth/validación de la API admin. El backend queda
> **cerrado y verificable** como producto de plataforma. **La Fase 4 construye
> encima la experiencia de operación:** una pantalla dedicada en
> `base-admin-web` para gestionar y monitorear flags, independiente de la
> pantalla de parámetros del sistema.
>
> **Qué se hizo en fases anteriores y se consume aquí:**
> - Fase 1: contrato de evaluación y semántica de scopes (el admin solo
>   configura; no evalúa en el browser).
> - Fase 2: API `/platform/feature-flags/` (CRUD, scopes, toggle, estados) con
>   `AdminTokenAuthentication` y cambio en caliente vía caché.
> - Fase 3: confianza en que las reglas de evaluación están probadas.
>
> **Qué queda como punto de partida de esta fase:**
> - No existe UI de feature flags en `base-admin-web` (solo parameters y otros
>   módulos de platform).
> - Hay que crear un módulo/feature propio (no anidar bajo configuration /
>   parameters).
> - Selectores de empresa/usuario y campos de ubicación (`country` / `state` /
>   `city`) para armar scopes.
>
> **Qué queda fuera de esta fase (y del plan actual):** exponer flags a
> `base-client-web`, primer caso de negocio concreto, políticas de caducidad
> automática y enforcement en CI.

**Objetivo:** permitir a un operador de plataforma gestionar el ciclo de vida
completo de las release flags (crear, acotar por empresa/usuario/ubicación,
activar/desactivar, certificar, archivar) desde `base-admin-web`, sin tocar BD ni
`.env`.

**Descripción detallada:** La UI es la cara operativa del sistema definido en
backend. El cliente admin consume únicamente la API platform. Los estados y
tipos se muestran de forma explícita para facilitar la limpieza de código
cuando una flag pasa a `CERTIFIED`. Los scopes de ubicación usan los mismos
valores que `Company.country` / `state` / `city`.

**Actividades:**

- [x] Crear módulo/feature dedicado (p. ej. `feature/platform/release` o
      `feature/admin/feature-flags`), **separado** de
      `feature/platform/configuration`.
- [x] Interfaces TypeScript alineadas al contrato de la API (flag, scope,
      tipos, estados).
- [x] `FeatureFlagService` (HTTP) hacia `${apiUrl}/platform/feature-flags/`.
- [x] Listado: key, nombre, tipo, status, enabled, resumen de scopes,
      fechas.
- [x] Indicadores visuales de ciclo de vida (especialmente `CERTIFIED` como
      recordatorio de retirar código viejo; `DISABLED` como kill-switch).
- [x] Crear / editar flag: key, name, description, `flag_type`, `status`,
      `enabled`, owner opcional.
- [x] Gestión de scopes en el formulario:
      - `COMPANY`: selector de empresas (reutilizar listados platform existentes).
      - `USER`: selector de usuarios de plataforma/empresa según API disponible.
      - `COUNTRY` / `STATE` / `CITY`: inputs o selectores de valor de ubicación
        (alineados a los campos de `Company`).
- [x] Acciones rápidas: toggle `enabled`, pasar a `DISABLED`, marcar
      `CERTIFIED`, `ARCHIVED`.
- [x] Manejo de estados de UI (loading, error, success) y mensajes del
      envelope `wrap_response`.
- [x] Entrada de menú / ruta de navegación en el admin, etiqueta clara
      (“Feature flags” / “Liberación de features”), no mezclada con
      “Parámetros”. Ubicada como pestaña del menú **Soporte**, con i18n.
- [x] Verificación manual: crear flag, acotar por `COUNTRY` o `COMPANY`,
      activar, confirmar que el backend evalúa en caliente (smoke con un use
      case de prueba o test de API).

**Definición de Done de la Fase 4:**

- [x] Un admin puede completar el ciclo `DRAFT` → `ACTIVE` → `DISABLED` /
      `CERTIFIED` → `ARCHIVED` desde la UI.
- [x] Puede asociar scopes `COMPANY`, `USER`, `COUNTRY`, `STATE`, `CITY`.
- [x] La pantalla es independiente de la de parámetros del sistema.
- [x] No se exponen flags ni endpoints de evaluación al cliente operativo
      (`base-client-web`).

### Ubicación en UI

- Menú lateral: **Soporte** (`/admin/support`)
- Pestaña: **Feature flags** (`admin.support.tabs.feature-flags`)
- Componente: `wa-admin-feature-flags`
