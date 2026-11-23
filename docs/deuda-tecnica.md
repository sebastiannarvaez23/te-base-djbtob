# Deuda técnica — base

Registro de la deuda **asumida a propósito** en este backend. Si una entrada
es compartida con Neurana, la versión canónica (criterios, orden completo y
reversión) vive en
`ne-core-mon/docs/architecture/deuda-tecnica.md`. Aquí solo se resume lo que
toca a la base.

| ID | Tema | Severidad | Estado |
|---|---|---|---|
| DT-001 | Modos de transición del protocolo base ↔ NE | Alta (seguridad) | Abierta |
| DT-002 | `invoice.rejected` sin emisor en Neurana | Media (funcional) | Abierta |

---

## DT-001 — Modos de transición del protocolo base ↔ NE

Canónico: `ne-core-mon/docs/architecture/deuda-tecnica.md#dt-001`.

la base ya se autentica con `private_key_jwt` (Ed25519) y verifica webhooks v2
contra la JWKS de Neurana. Para desplegar sin corte siguen activos dos
mecanismos de secreto compartido:

| Setting | Encendido significa |
|---|---|
| `NE_PRODUCT_CLIENT_SECRET` (no vacío) | El cliente puede autenticarse con `client_secret` si no hay llave privada |
| `NE_WEBHOOK_ALLOW_V1=True` (default) | Se aceptan webhooks firmados solo con HMAC v1 (`NE_WEBHOOK_SECRETS`) |

Mientras sigan activos, quien tenga el secreto de webhook puede falsificar
eventos fiscales hacia la base.

### Evidencia antes de apagar

- El arranque muestra `ERP : OK`, es decir, el health autenticado responde.
- `python manage.py generate_ne_product_key --show` muestra el mismo `kid` que
  Neurana tiene registrado para el producto.
- **7 días** de logs `neurana_webhook ... scheme=v2`, sin ningún `scheme=v1`.
- Sin alertas de la campanita por backlog fiscal ni por *dead letters*.

### Pasos de la base dentro del orden global

1. **Paso 1** (antes que todo): vaciar `NE_PRODUCT_CLIENT_SECRET` y reiniciar
   web, workers y beat.
2. Neurana apaga `ECOSYSTEM_ALLOW_CLIENT_SECRET`, `ECOSYSTEM_ALLOW_HS256` y
   `ECOSYSTEM_WEBHOOK_SIGN_V1` (pasos 2–4).
3. **Paso 5**: `NE_WEBHOOK_ALLOW_V1=False`, vaciar `NE_WEBHOOK_SECRETS` y
   reiniciar. Un webhook firmado solo con v1 debe responder `401 ECO_005`.

**Nunca** apagar `NE_WEBHOOK_ALLOW_V1` antes de que Neurana deje de firmar
solo con v1. Si se hace, los webhooks se rechazan; las facturas quedan
`pending` hasta que la reconciliación diaria las recupere.

### Cierre en código

Cuando esté apagado en producción:

- Default de `NE_WEBHOOK_ALLOW_V1` a `False` en `base/settings/base.py`.
- Quitar el fallback v1 de `neurana_webhooks._verify` y el `client_secret` de
  `ecosystem_client.build_ecosystem_client`.
- Limpiar `base/settings/.env.ex`.

---

## DT-002 — `invoice.rejected` sin emisor en Neurana

Canónico: `ne-core-mon/docs/architecture/deuda-tecnica.md#dt-002`.

la base ya procesa `invoice.rejected` (marca `fiscal_status=rejected`), pero
Neurana aún no lo emite. Hoy solo se detectan rechazos síncronos: un 4xx al
emitir lo marca el relay de `fiscal_outbox`. No requiere cambios en la base
cuando se pague.
