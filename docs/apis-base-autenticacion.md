# APIs de la base — Autenticación

Guía técnica para que un sistema externo obtenga un token de acceso y lo use
en sus llamadas a la API de la base.

---

## 1. Flujo

La autenticación sigue el estándar **OAuth 2.0, flujo `client_credentials`**
(comunicación entre sistemas, sin usuario humano):

```
Tu sistema                                La base
    │  1. POST /api/v1/oauth/token/           │
    │     client_id + client_secret  ───────► │
    │  ◄──────────────────────  access_token  │
    │                                         │
    │  2. GET /api/v1/<recurso>/              │
    │     Authorization: Bearer <token> ────► │
    │  ◄─────────────────────────  respuesta  │
```

Cuando el token vence, se solicita uno nuevo con las mismas credenciales.

---

## 2. Antes de empezar

Necesitas:

1. Una **aplicación de integración activa**, creada por el administrador de tu
   empresa en la base (**Bodega → Integraciones → Nueva aplicación**).
2. Su **`client_id`** y **`client_secret`**. El secreto se muestra una sola vez
   al crear la aplicación; si se pierde, el administrador debe generar uno
   nuevo.
3. La **URL base** de tu empresa en la base (`{URL_BASE}` en esta guía).

---

## 3. Solicitar el token

```http
POST {URL_BASE}/api/v1/oauth/token/
Content-Type: application/json
Accept: application/json
```

```json
{
  "grant_type": "client_credentials",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>",
  "scope": "warehouse.api.location-list"
}
```

| Campo | Obligatorio | Valor |
|-------|:-----------:|-------|
| `grant_type` | Sí | Siempre `client_credentials` |
| `client_id` | Sí | Identificador de la aplicación |
| `client_secret` | Sí | Secreto de la aplicación |
| `scope` | No | Permisos que necesitas, separados por espacio |

- Esta petición **no** lleva cabecera `Authorization`.
- No envíes campos adicionales: la petición se rechaza.
- **Sin `scope`**: el token incluye todos los permisos disponibles para la
  aplicación.
- **Con `scope`**: el token incluye solo los permisos indicados; si alguno no
  está disponible para la aplicación, la petición se rechaza.

---

## 4. Respuesta

`200 OK`

```json
{
  "type": "success",
  "status_code": 200,
  "message": "Access token issued.",
  "resolved_at": "2026-10-05 23:43:56",
  "data": {
    "access_token": "<token>",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "warehouse.api.location-list"
  }
}
```

| Campo (`data`) | Significado |
|----------------|-------------|
| `access_token` | Token a enviar en cada llamada |
| `token_type` | Siempre `Bearer` |
| `expires_in` | Segundos de validez del token |
| `scope` | Permisos incluidos en el token, separados por espacio |

> El token viene dentro de `data`, no en la raíz de la respuesta.

Trata el `access_token` como un valor opaco: no dependas de su formato ni de su
contenido.

---

## 5. Usar el token

Envía el token en la cabecera `Authorization` de cada llamada:

```http
GET {URL_BASE}/api/v1/<recurso>/
Authorization: Bearer <access_token>
```

- Formato exacto: `Bearer`, un espacio y el token.
- Cada endpoint requiere un permiso; si el token no lo incluye, la respuesta es
  `403`.
- Un token puede dejar de ser válido antes de `expires_in` (por ejemplo, si el
  administrador deshabilita la aplicación). Tu sistema debe estar preparado
  para recibir `401` en cualquier momento.

---

## 6. Errores

Todas las respuestas de error siguen este formato:

```json
{
  "type": "error",
  "status_code": 401,
  "message": "Invalid credentials",
  "detail": "...",
  "resolved_at": "2026-10-05 23:44:43",
  "error": {
    "code": "AUTH_001",
    "trace_id": "01a10e74-8f3e-7004-83c8-3954ba29d50c"
  }
}
```

Los errores de formato del cuerpo devuelven además una lista `errors` con el
campo y el motivo:

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

### 6.1 Al solicitar el token

| HTTP | Código | Causa | Qué hacer |
|------|--------|-------|-----------|
| 400 | lista `errors` | Falta un campo, tiene un formato inválido o sobra un campo | Corregir el cuerpo según la sección 3 |
| 400 | `VAL_001` | `grant_type` distinto de `client_credentials` | Enviar `client_credentials` |
| 401 | `AUTH_001` | Credenciales incorrectas | Verificar `client_id` y `client_secret` |
| 403 | `AUTH_008` | La aplicación está deshabilitada o revocada | Contactar al administrador de tu empresa |
| 403 | `AUTH_010` | Un permiso solicitado no está disponible para la aplicación | Ajustar `scope` o pedir el permiso al administrador |
| 429 | — | Demasiadas peticiones | Esperar y reintentar con espera progresiva |

### 6.2 Al usar el token

| HTTP | Causa | Qué hacer |
|------|-------|-----------|
| 401 | Token vencido o ya no válido | Solicitar un token nuevo y repetir la llamada una vez |
| 403 | El token no incluye el permiso que exige el endpoint | Pedir el permiso al administrador y solicitar un token nuevo |
| 429 | Demasiadas peticiones | Esperar y reintentar con espera progresiva |

Usa siempre `status_code` y `error.code` para decidir; el texto de `message` y
`detail` puede cambiar. Si contactas a soporte, incluye el `trace_id`.

---

## 7. Ejemplo con cURL

```bash
curl -X POST "$URL_BASE/api/v1/oauth/token/" \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "'"$BASE_CLIENT_ID"'",
    "client_secret": "'"$BASE_CLIENT_SECRET"'"
  }'
```

---

## 8. Buenas prácticas

- **Reutiliza el token** hasta poco antes de que venza; no solicites uno por
  cada llamada.
- **Ante un `401`**, solicita un token nuevo y reintenta **una sola vez**; si
  vuelve a fallar, detén el proceso y alerta.
- **No reintentes en bucle** `AUTH_001` ni `AUTH_008`: requieren intervención.
- **Protege las credenciales**: guárdalas en un gestor de secretos o variables
  de entorno; nunca en el código, en logs ni en repositorios.
- **Usa siempre HTTPS.**
- **Solicita solo los permisos** que tu proceso necesita.
- **Si sospechas que el secreto se filtró**, pide al administrador que genere
  uno nuevo; el anterior deja de funcionar de inmediato.
