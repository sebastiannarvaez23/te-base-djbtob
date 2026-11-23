# APIs de la base — Documentación general

Qué son las APIs de la base, para qué sirven y cómo se conecta un sistema de tu
empresa. Para el detalle de la autenticación ver
[`apis-base-autenticacion.md`](./apis-base-autenticacion.md).

---

## 1. Qué son

La base expone las APIs de plataforma y de tenant. El dominio de negocio
no viene incluido: cada producto agrega sus recursos sobre este mismo contrato
de autenticación, tenant y errores.

---

## 2. Conceptos clave

| Concepto | Qué es |
|----------|--------|
| **Aplicación de integración** | El registro de un sistema externo en la base (p. ej. "Middleware SAP"). Tiene nombre, ambiente, permisos y credenciales propias. |
| **Credenciales** | `client_id` (identificador) y `client_secret` (secreto). El secreto se muestra **una sola vez**. |
| **Permiso de API (scope)** | Lo que la aplicación puede hacer, p. ej. `warehouse.api.location-list` (listar almacenes). |
| **Ambiente** | `CLIENT_TEST` (pruebas) o `CLIENT_PROD` (producción). Usa credenciales distintas para cada uno. |
| **Token de acceso** | Credencial temporal que tu sistema envía en cada llamada. |

---

## 3. Cómo conectarse

### 3.1 Registrar la aplicación

El administrador de tu empresa entra a **Bodega → Integraciones** en la base y
crea una **Nueva aplicación**:

1. Nombre y descripción del sistema que se va a conectar.
2. Ambiente (`CLIENT_TEST` o `CLIENT_PROD`).
3. Permisos de API que necesita (solo los indispensables).

Al guardar, la base muestra el `client_id` y el `client_secret`. **Copia el
secreto en ese momento**: no se puede volver a consultar. Si se pierde, el
administrador genera uno nuevo.

### 3.2 Obtener un token

```http
POST {URL_BASE}/api/v1/oauth/token/
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

Respuesta:

```json
{
  "type": "success",
  "status_code": 200,
  "message": "Access token issued.",
  "data": {
    "access_token": "<token>",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "warehouse.api.location-list"
  }
}
```

Cuando el token vence (`expires_in`, en segundos), se solicita uno nuevo con las
mismas credenciales. Detalle completo, errores y ejemplos de código en la
[guía de autenticación](./apis-base-autenticacion.md).

### 3.3 Llamar a la API

```http
GET {URL_BASE}/api/v1/<recurso>/
Authorization: Bearer <access_token>
```

Cada endpoint requiere un permiso. Si el token no lo incluye, la respuesta es
`403`.

`{URL_BASE}` es la dirección de tu empresa en la base; los tokens solo son
válidos en esa dirección.

---

## 4. Permisos de API

- A una aplicación solo se le pueden asignar **permisos de API**.
- Solo están disponibles los permisos que incluye **la suscripción de tu
  empresa** y que el administrador que los asigna tiene en su rol.
- Si la suscripción cambia y un permiso deja de estar incluido, los nuevos
  tokens ya no lo tendrán.

Al crear o editar una aplicación desde la base, estos son los avisos posibles:

| Código | Significado |
|--------|-------------|
| `INT_016` | Se seleccionó algo que no es un permiso de API |
| `INT_015` | La suscripción o el rol no incluyen alguno de los permisos |

---

## 5. Estados de una aplicación

| Acción | Efecto |
|--------|--------|
| **Deshabilitar** | Pausa temporal: la aplicación no puede autenticarse y sus tokens dejan de funcionar. |
| **Habilitar** | Vuelve a operar con las mismas credenciales. |
| **Generar nuevo secreto** | Entrega un `client_secret` nuevo (se muestra una vez); el anterior deja de funcionar. |
| **Revocar** | Corte definitivo: no se puede reactivar ni editar. |
| **Eliminar** | Disponible solo para aplicaciones revocadas. |

Estas acciones las realiza el administrador de tu empresa desde la base.

---

## 6. Formato de respuesta

**Éxito**

```json
{
  "type": "success",
  "status_code": 200,
  "message": "OK",
  "resolved_at": "2026-10-05 23:43:56",
  "data": { }
}
```

Los listados paginados devuelven en `data`: `items`, `total`, `page`,
`page_size` y `total_pages`.

**Error**

```json
{
  "type": "error",
  "status_code": 403,
  "message": "Scope not granted",
  "detail": "...",
  "resolved_at": "2026-10-05 23:44:43",
  "error": {
    "code": "AUTH_010",
    "trace_id": "01a10e74-8f3e-7004-83c8-3954ba29d50c"
  }
}
```

**Error de formato del cuerpo (400)**

```json
{
  "type": "error",
  "status_code": 400,
  "message": "Request body validation error.",
  "errors": [
    { "field": "client_secret", "code": "REQUIRED", "detail": "..." }
  ]
}
```

- Usa `status_code` y `error.code` para decidir; el texto puede cambiar.
- No envíes campos que el endpoint no documenta: la petición se rechaza.
- Si contactas a soporte, incluye el `trace_id`.

---

## 7. Errores más comunes

| Código | HTTP | Significado | Qué hacer |
|--------|------|-------------|-----------|
| `AUTH_001` | 401 | Credenciales incorrectas | Verificar `client_id` y `client_secret` |
| `AUTH_008` | 403 | Aplicación deshabilitada o revocada | Contactar al administrador de tu empresa |
| `AUTH_010` | 403 | Permiso no disponible para la aplicación | Ajustar `scope` o pedir el permiso |
| `VAL_001` | 400 | `grant_type` no soportado | Enviar `client_credentials` |
| — | 401 | Token vencido o ya no válido | Solicitar un token nuevo |
| — | 403 | El token no incluye el permiso del endpoint | Pedir el permiso y solicitar un token nuevo |
| — | 429 | Demasiadas peticiones | Esperar y reintentar con espera progresiva |

---

## 8. Buenas prácticas

- **Protege el `client_secret`**: gestor de secretos o variables de entorno;
  nunca en el código, logs ni repositorios.
- **Una aplicación por sistema y por ambiente**: puedes deshabilitar una sin
  afectar a las demás.
- **Mínimo privilegio**: asigna solo los permisos que el sistema usa.
- **Genera un secreto nuevo** periódicamente y ante cualquier sospecha de
  filtración.
- **Reutiliza el token** hasta poco antes de que venza.
- **Usa siempre HTTPS.**
