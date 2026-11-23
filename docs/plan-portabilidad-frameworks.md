# Plan de portabilidad — misma lógica, otro framework

Checklist de **todo** lo que `te-base-djbtob` y `te-base-djctoc` comparten a nivel de aplicación y plataforma. Sirve para reconstruirlo (Nest, Spring, FastAPI, etc.) sin rediseñar el producto.

**No se porta.** PostgreSQL (`wadb` OLTP + `wadw` analítica), Redis (caché, locks, anillo de incidencias, logs en vivo, broker), Celery/RedBeat o el worker equivalente, almacenamiento de objetos (MinIO), SMTP/Resend, el runtime de inferencia (proceso aparte) y los hosts `app.base.local` / `admin.base.local`.

**Única bifurcación entre las dos bases.**

- [ ] `djbtob`: un schema PostgreSQL por empresa. El host elige el schema. `schema_name` crea el schema.
- [ ] `djctoc`: una sola base. La empresa sale del usuario autenticado. `schema_name` es solo una etiqueta. No hay `CREATE SCHEMA`.

El resto de esta lista es idéntico. Cada ítem se marca cuando el framework nuevo cumple el contrato, no cuando “existe una tabla parecida”.

Criterio de paridad: mismas rutas bajo `/api/v1/`, mismas cookies, mismo sobre de respuesta, mismos códigos de error, mismas máquinas de estado. Los frontends (`base-client-web`, `base-admin-web`, `base-docs-web`) no se reescriben.

---

## 0. Contratos transversales

- [x] Prefijo HTTP `/api/v1/`. OpenAPI publicado (swagger + redoc).
- [x] Sobre de éxito: `{ status_code, message, resolved_at, data }`.
- [x] Sobre de error 400: `errors[{ field, code, detail }]`. Nunca un 500 por input inválido.
- [x] Catálogo único de errores: código estable (`AUTH_001`, `SUB_…`, `COMP_…`), `http_status`, `message` y `detail` en inglés, texto de operador en español. Dos causas distintas, dos códigos. El mensaje dice qué no se puede hacer y qué revisar; no UUID, no ORM, no “does not exist”.
- [ ] Sync del catálogo hacia `errors.json` (en/es) de los tres frontends.
- [ ] Validación de entrada en el borde: body, query, path. Tipos, largo máximo, choices/pattern, UUID, email. Rechazar campos desconocidos. Listas, decimales y objetos anidados declarados. Nada de leer el body crudo salvo las excepciones de abajo.
- [ ] Excepciones de body: webhook con firma, multipart (el archivo se valida en la vista; el resto del form sí va tipado), POST/PATCH sin body (toggle, logout, confirm, sync).
- [x] Salida: contrato tipado serializado a JSON. Sin capa de serializers paralela.
- [x] Header `X-Request-ID` en cada request. `X-Auth-Context: admin|client` cuando las dos sesiones conviven.
- [x] Cookies (dominio `.base.local`, SameSite Lax): `access_client`, `refresh_client`, `device_client`, `access_admin`, `refresh_admin`.
- [x] JWT de acceso con `user_id`, `user_type` (`client`|`admin`), `schema_name` (etiqueta de empresa), `sid`, `access_mode`, `username`.
- [x] Refresh opaco, rotación en cada uso, revocación, TTL distinto si “recordarme”. El refresh silencioso no cuenta como actividad.
- [ ] PKs UUID. Borrado de FK que no cascadea en datos de negocio (auditoría). Transacción atómica cuando cambia estado que debe quedar consistente. Cada cambio de ese estado deja rastro.
- [ ] Aislamiento por empresa: en `djctoc` filtrar por `company_id` del JWT; en `djbtob` el schema ya aísla. Un admin de plataforma no es usuario de empresa. Un usuario de empresa no ve billing global ni datos de otra empresa.
- [x] Logs de aplicación nunca rompen el request (best-effort, try/except).
- [ ] Redacción de secretos y PII en logs y en prompts.
- [ ] Jerarquía de código: mundo (`client` | `platform` | `handbook`) → feature extraíble → familia → entidad. La arquitectura por capas vive solo en la entidad. Un caso de uso = un `execute`. El dominio no importa infraestructura.

---

## 1. Identidad y sesión

### Cliente (quien usa el producto)

- [ ] Usuario de empresa: email, username, activo, rol, empresa, `email_verified_at`, perfil (nombre, documento, fecha de nacimiento).
- [ ] Login con contraseña. Si el correo no está verificado → `AUTH_007`.
- [ ] Confirmación de email por token de un solo uso. Reenvío.
- [ ] Alta de colaboradores con enlace de activación y set de contraseña.
- [ ] Recuperación de contraseña (token, política de clave).
- [ ] 2FA por email OTP solo si el parámetro lo enciende y el device serial es desconocido. OTP 6 dígitos, TTL 5 min, 5 intentos, solo se persiste HMAC. El serial va atado al user id.
- [ ] Challenge: emitir, rotar (no reinicia intentos), recordar “recordarme”, verificar, rechazar OTP malo, IP distinta, empresa distinta, usuario inactivo, empresa cerrada, challenge vencido o desconocido.
- [ ] Device de confianza (`device_client`). Revocar device.
- [ ] IP: ignorar `X-Forwarded-For` salvo flag de confianza. Geo headers igual.
- [ ] Sesiones activas listables y revocables. `sid` en Redis; si no existe la sesión, el access token no vale.
- [ ] Logout limpia cookies. Refresh 401 limpia cookies.
- [ ] Rol de empresa `Administrator` recibe todas las features activas. El resto solo las que se le asignen.
- [ ] Permisos de rol: módulos y funcionalidades, activar/desactivar cada uno.
- [ ] Historial de accesos y auditoría de cambios de usuarios.
- [ ] Preferencias de usuario: tema, idioma, zona horaria, formato de fecha.
- [ ] Perfil y foto en el bucket de objetos (bucket `base`).

### Plataforma (equipo de la base)

- [ ] `AdminUser` distinto de `User`. Login, refresh, logout, cookies admin.
- [ ] CRUD de admins. Comando para crear el primer admin.
- [ ] Roles admin, módulos admin, secciones, funcionalidades admin.
- [ ] Sesiones admin listables y revocables.
- [ ] Perfil admin y su bucket de objetos.
- [ ] Parámetros de seguridad del admin (juego distinto al de la empresa).
- [ ] Django admin (o equivalente) solo si el host del `Domain` de esa empresa coincide; si no, logout.

### Apps que se conectan a la plataforma

- [ ] Principal de integración (no es un usuario): JWT propio, `client_id`, no llena `user_id` de auditoría.
- [ ] OAuth de conexiones (autorización de conectores).

---

## 2. Autorización (el contrato que el frontend ya consume)

Catálogo de features de empresa. Claves que hay que seguir emitiendo:

- [ ] `users_roles.*` — crear/editar/desactivar usuarios, crear/editar roles, asignar roles, permisos por módulo y por funcionalidad, historial, 2FA, recuperación, política de clave, sesiones, auditoría de cambios.
- [ ] `security.users.view|create|edit|toggle-active`
- [ ] `security.permissions.view|create-role|toggle-role|edit-role|save|view-features|toggle-module|toggle-feature`
- [ ] `integrations.erp-integration|webhooks|integration-logs|data-mapping|oauth`
- [ ] `audit.event-logging|advanced-filters|log-export|critical-alerts|entity-change-history|user-traceability|access-audit|config-change-audit|configurable-retention|audit-reports`
- [ ] `settings.company.view|company-config|printers-devices|notifications-config|document-templates|currency-config|security-params|backup-config|ui-customization|subscription-billing`
- [ ] `settings.profile.view|edit`, `settings.preferences.view|change-theme|change-language|change-timezone|change-date-format`
- [ ] `settings.subscription.view|upgrade|cancel|apply-voucher|view-voucher-applied`
- [ ] `settings.payment-methods.view|create|edit|toggle|delete`
- [ ] `assistant.chat`
- [ ] Sync del registry → tablas de módulo + funcionalidad. Lo que ya no está en el registry se desactiva, no se borra.
- [ ] El admin de empresa hereda el complemento de la licencia; los demás roles solo si se les asigna.
- [ ] Gate por request: miembro de la empresa + feature de la suscripción + modo de acceso (recuperación de billing solo deja pasar las features de cobro).
- [ ] Cupo por entidades activas. Referencia: usuarios. El alta rechaza cuando el cupo del plan está lleno. El contador de por vida vive en Redis y se re-siembra desde la base si falta.
- [ ] Grants por entidad: el producto registra los `entity_type`; mientras no haya, todo tipo se rechaza. Purga de grants cuyo usuario ya no está o cuyo registro ya no existe. Un usuario inactivo conserva sus grants.
- [ ] Filtros de módulo por usuario. El catálogo de la base responde “ese registro no está disponible” hasta que el producto registre entidades.
- [ ] Feature flags con scopes: usuario, empresa, país, estado, ciudad. Evaluación best-effort.

Códigos de este bloque: `PERM_*`, `ROLE_*`, `SESSION_*`, `USER_*`, filtros de módulo, grants, `SECTION_*`, `MODULE_*`, `FUNC_*`.

---

## 3. Empresa y alta

- [ ] `Company`: nombre, NIT único si viene informado, dirección, ciudad, etiqueta `schema_name` única, lifecycle.
- [ ] `Domain`: host, `is_primary`, pertenece a una empresa.
- [ ] Lifecycle: `ACTIVE` → `CLOSED` → `PENDING_PURGE` → `GONE`.
- [ ] Cierre: motivo, admin que cierra, `purge_after`, legal hold + motivo. Con legal hold no se purga.
- [ ] Exportación atestiguada (quién, cuándo, object key) antes de purgar.
- [ ] Purga: tumba usuarios, desengancha filas fiscales (conserva NIT y nombre en la factura/cargo), ancla `ClosedTenantRecord`, marca `GONE`, limpia satélites de auth.
- [ ] En `djbtob` la purga además tira el schema. En `djctoc` no hay schema que tirar.
- [ ] No se cierra ni se purga la fila etiqueta `public`.
- [ ] Onboarding en 5 pasos, en este orden: `company` → `admin_user` → `subscription` → `payment` → `confirmation`.
- [ ] Estados del registro: `in_progress`, `completed`, `expired`, `failed_provisioning`.
- [ ] Finalize crea empresa, dominio, suscripción y usuario admin, y manda el correo de confirmación. Login bloqueado hasta confirmar.
- [ ] Bono opcional en el finalize. Sin bono, cero redenciones.
- [ ] Purga diaria de registros `in_progress` abandonados, `failed_provisioning` viejos y tokens de confirmación ya usados.
- [ ] Purga diaria de empresas cuyo único usuario nunca confirmó el correo, creadas hace más de 7 días, sin cobro capturado ni factura pagada.
- [ ] Parámetros de cierre de empresa (gracia, etc.) como parámetros de plataforma, no hardcode.
- [ ] Registro de la empresa como cliente facturable hacia Neurana.

Códigos: `COMP_*` (incluye dominio que no corresponde), `ONB_*`.

---

## 4. Billing

### Plan y periodo

- [ ] Plan (`Subscription`): precio, activo, descuento anual, módulos y funcionalidades que habilita, límites, complementos.
- [ ] Periodo por empresa (`CompanySubscription`): `active | cancelled | expired | suspended`. Un periodo activo por empresa.
- [ ] Intervalo, `auto_renew`, vigencia, plan pendiente (downgrade programado) + intervalo pendiente.
- [ ] Upgrade inmediato (cobra y abre periodo). Cancel. Reactivar. Reintentar pago suspendido.
- [ ] Downgrade: se agenda; el job diario lo materializa al vencer la vigencia (cobra el plan menor, periodo nuevo +30 días).
- [ ] Renovación diaria: vigencia vencida, sin cambio pendiente, `auto_renew` on → mismo plan, +30 días.
- [ ] Si `auto_renew` está off y no hay cambio pendiente, el periodo pasa a `expired`.
- [ ] Cambio de status administrativo.
- [ ] Catálogo público de planes (sin auth) para la landing y el onboarding.
- [ ] Cache de suscripción por empresa. Si Redis cae, se consulta la base.

### Cobro

- [ ] Método de pago: `card | bank_transfer | pse`. Alta, edición, activar, borrar. Token del gateway, nunca el PAN.
- [ ] Cargo. Estados: `pending → processing → requires_action | authorized → captured`, y `failed | canceled | refunded | partially_refunded | disputed`.
- [ ] Terminales: `failed`, `canceled`, `refunded`. Exitosos: `captured`, `authorized`, `partially_refunded`.
- [ ] Proveedor de gateway intercambiable. El adapter traduce nombres externos a este enum. Next action para 3DS/PSE.
- [ ] Webhook del gateway con firma y cuerpo crudo. Idempotencia por evento.
- [ ] Intentos de cobro (operación + resultado) como bitácora.

### Factura y fiscal

- [ ] Factura ligada a la empresa. Al purgar la empresa se conserva NIT y nombre y se suelta el FK.
- [ ] Emisión automática al capturar un pago, con snapshot de la promoción.
- [ ] Outbox fiscal hacia Neurana: lease con skip-locked, backoff, relay cada ~30 s, salud cada 5 min, reconciliación diaria de pendientes.
- [ ] Webhook de vuelta del ecosistema (documento aceptado/rechazado).
- [ ] Modo local: la reconciliación no llama a la red.

### Reembolso

- [ ] Ticket con número único. Kind: `full | difference`.
- [ ] Estados: `pending → accepted → processing → completed | failed`, o `rejected`.
- [ ] El payout y el cambio de plan corren solo después de la aprobación admin.
- [ ] Aviso a la campanita de la empresa.

### Promociones

- [ ] Voucher: `ACTIVE → REDEEMED | EXPIRED`. Ventana de redención. Alcance `OPEN` o `COMPANY` (si es COMPANY, la empresa es obligatoria; si es OPEN, no lleva empresa).
- [ ] Meses de beneficio entre 1 y 36.
- [ ] Redención en el alta y sobre una suscripción viva.
- [ ] Job diario: vencer vouchers. Job siguiente: revertir regalos cuyo `benefit_end` pasó (volver al plan anterior si quedó anotado).
- [ ] Plantillas de correo del bono y de la factura.

Códigos: `SUB_*`, `LIMIT_*`, `INVOICE_*`, `PAY_*`, `REFUND_*`, `PROMO_*`, `COMPLEMENT_*`, `FIS_*`.

---

## 5. Comunicación

- [ ] Correo: puertos `smtp | resend | fake`, fallback si el primario falla, headers de marca (`Base <noreply@base.local>`).
- [ ] Plantillas versionadas. Remitente por defecto. Reparación de la plantilla de baja de empresa.
- [ ] Campanita de la empresa: lista, archivar, compartir un recurso con usuarios de la empresa.
- [ ] Campanita admin (outbox): alcance `SINGLE_USER | COMPANY_USERS | ALL_TENANTS`. El fan-out agrupa destinatarios por etiqueta de empresa y entrega en la misma base (o en el schema, en `djbtob`).
- [ ] Kinds: directo, empresa, broadcast. Nivel INFO/SUCCESS/…
- [ ] Bienvenida al ejecutivo y al colaborador al activar la cuenta.
- [ ] WS `ws/client/inbox/` y `ws/platform/inbox/`. Cookie JWT en el handshake.
- [ ] Catálogo de recursos compartibles. Vacío hasta que el producto registre tipos. Sync de ese catálogo.

Códigos: `EMAIL_*`, `DOC_*` (plantillas de documento), `NOTIF_*`.

---

## 6. Catálogos de plataforma

- [ ] Parámetros de empresa: tipo + parámetro. Juego mínimo de seguridad (2FA, política de clave, confirmación de email).
- [ ] Parámetros de admin: tipo + parámetro. Juego mínimo de seguridad admin.
- [ ] Landing: secciones públicas y CRUD admin. Testimonios públicos y CRUD. Módulo CRM asociado.
- [ ] Geografía: país, departamento, ciudad. Endpoints públicos de solo lectura y CRUD admin.
- [ ] Moneda y país de moneda. Sync de catálogo.
- [ ] Políticas legales. Aceptación por empresa/usuario. Lectura pública de la vigente.
- [ ] Plantillas de documento (la de producto, no el correo).
- [ ] Flags de release (además de los scopes del apartado 2).

Códigos: `PARAM_*`, `ADM_PARAM_*`, `LAND_*`, `TESTIM_*`, `FLAG_*`, `GEO_*`, `POLICY_*`.

---

## 7. Integraciones

- [ ] Catálogo global de conectores. El template trae el fake y el webhook de entrada. El producto registra los demás (ERP, etc.).
- [ ] Conexión por empresa: key, nombre, ambiente `PROSANDBOX | CLIENT_TEST | CLIENT_PROD`, config, estado `ACTIVE | PAUSED | DEGRADED | ERROR`, cron, último error.
- [ ] Secreto cifrado (`INTEGRATIONS_SECRET_KEY`). Nunca en logs.
- [ ] Mapeo de campos por conexión.
- [ ] Puerto: `pull_entities`, `push_entities`, test de conexión. Idempotencia. Circuit breaker: un conector caído no tumba el producto.
- [ ] Conflictos: gana el sistema local en `status` y `quantity`.
- [ ] Salud agregada para soporte: cuántas conexiones activas, degradadas, en error, y el detalle de las dañadas.
- [ ] Logs de integración consultables (`integrations.integration-logs`).

Códigos: `INT_*`.

---

## 8. Asistente e IA

- [ ] Chat por usuario: conversación, mensaje, tool call, agent run. Feature `assistant.chat`.
- [ ] WS `ws/assistant/`: el turno corre en un hilo, la cola empuja `thinking → tool → typing → token → done | error`.
- [ ] Credenciales BYOK cifradas por empresa. HITL: la tool peligrosa espera aprobación humana.
- [ ] Cancelación de un run en curso.
- [ ] Registry de tools **vacío** en la base. El producto registra las suyas. Una tool desconocida es `AI_UNKNOWN_TOOL`.
- [ ] Política de runtime, estado on/off, kill switches `AI_ENABLED` / `OR_ENABLED` / `ML_ENABLED`.
- [ ] Proveedor `fake` por defecto (tests y clone sin modelo). Camino real: proceso SLM local. Anthropic es opcional.
- [ ] Toda llamada es best-effort: si el runtime cae, el producto sigue y se devuelve el fallback.
- [ ] No mezclar empresas en un prompt. Redactar antes de enviar.
- [ ] Usage: tokens, modelo, proveedor, latencia, empresa. Logger `app.ai`.
- [ ] Ajustes admin del asistente (tools habilitadas = ninguna hasta que haya catálogo).
- [ ] Enrutamiento de modelos, capacidades on/off, evals, observación de runs recientes.
- [ ] Uso 24 h (mensajes, conversaciones, errores) para el panel admin.
- [ ] Comando de evals.

Códigos: `AI_*`.

---

## 9. Logging

- [ ] Cuatro tipos configurables: `audit`, `operations`, `integration`, `security`.
- [ ] Audit log: entidad, id, acción, descripción, cambios, actor. Un principal de integración no ocupa `user_id`.
- [ ] Security log: tipo de evento, usuario destino, recurso, detalle.
- [ ] Operaciones: el modelo histórico se sigue llamando `WarehouseEvent`. No renombrarlo al portar si los frontends o el DW lo leen.
- [ ] Integration log.
- [ ] Retención por tipo, job/comando propio.
- [ ] La escritura va en savepoint propio: un fallo de log no revierte el caso de uso.

---

## 10. Soporte

### Incidencias

- [ ] Un 500 de un usuario de empresa puede volverse incidencia. El middleware guarda las últimas 10 transacciones de la sesión en Redis (`sess_txns:<sid>`).
- [ ] El 500 congela snapshot (10 previas + la fallida + stack) bajo un token opaco con TTL y añade `error.incident = { token, report_url }`.
- [ ] `POST /api/v1/incidents/report/` (JWT cliente) materializa la incidencia, idempotente por token, y avisa al admin en best-effort.
- [ ] Alta manual y desde contexto de frontend.
- [ ] Estados: `open → in_progress → resolved | closed | discarded`.
- [ ] Adjuntos en el object storage. Purga de terminales por retención (días configurables) borra también los objetos.
- [ ] Redis caído no rompe el request. Buffers acotados. El snapshot es PII de admins.
- [ ] Admin: listar, filtrar, cambiar estado, comentar.

### Tareas

- [ ] Cada task deja run + steps. Compensaciones LIFO si falla.
- [ ] Monitor admin + WS `ws/platform/task-monitor/`.
- [ ] Incidente también cuando una task falla (mismo sistema de incidencias).

### Logs en vivo

- [ ] Handler que empuja al anillo Redis. WS `ws/platform/live-logs/` solo admin.

### Chat de soporte

- [ ] Sesión: `QUEUED → ACTIVE → AWAITING_RATING → CLOSED`, o `CANCELLED`.
- [ ] Emisor `CLIENT | AGENT`. Mensajes. Rating al cerrar.
- [ ] Timeout de cola y TTL de rating. Job cada 60 s.
- [ ] WS cliente `ws/support/sessions/` y WS admin `ws/platform/support/sessions/`.
- [ ] Ajustes: minutos de espera, TTL de rating.

Códigos: `INC_*`, `TASK_*`, `SUP_*`.

---

## 11. Handbook (documentación de la plataforma)

- [ ] Audiencias: `public`, `admin`, `wms` (audiencia de producto; el nombre quedó así).
- [ ] Una página es visible si la audiencia coincide y, cuando lleva `feature_key`, el viewer tiene esa feature.
- [ ] Árbol, página, CRUD de catálogo.
- [ ] Change request de una página (gobierno).
- [ ] Ingesta.
- [ ] Auth dual: el mismo árbol acepta cookie admin o cookie cliente. Sin contexto, gana la sesión admin.
- [ ] Features de admin propias del handbook (comando que las asegura).

Códigos: `HB_*`.

---

## 12. Analítica (`wadw`, no la base OLTP)

- [ ] Alias `analytics` con Postgres normal. El router manda solo las apps de control a `wadw` y niega las apps OLTP ahí.
- [ ] Migrar ese alias con un comando aparte (`migrate_analytics`), no con el migrate de la OLTP.
- [ ] Schemas internos del DW: `ctl`, `stg`, `dw` (son del warehouse, no de las empresas).
- [ ] Dimensión fecha cargable por rango.
- [ ] Dimensión empresa, sync desde OLTP.
- [ ] El ETL no es parte de este checklist más allá del control plane ya existente: lock, skip si hay otro corriendo, extraer de OLTP, no mezclar empresas.

---

## 13. Tiempo real y tareas

Handshake WS, en este orden: cookie → JWT (admin o cliente) → etiqueta de empresa → consumer.

- [ ] `ws/client/inbox/`
- [ ] `ws/platform/inbox/`
- [ ] `ws/assistant/`
- [ ] `ws/platform/task-monitor/`
- [ ] `ws/platform/live-logs/`
- [ ] `ws/support/sessions/`
- [ ] `ws/platform/support/sessions/`

Beat (UTC, con `expires` para no reventar tras una caída):

- [ ] 03:00 onboarding vencido
- [ ] 03:30 empresas con email nunca confirmado
- [ ] 03:45 empresas cerradas listas para purgar
- [ ] 04:00 downgrades de suscripción
- [ ] 04:15 renovaciones
- [ ] 04:30 vencer bonos
- [ ] 04:45 revertir regalos
- [ ] cada 60 s sesiones de soporte estancadas
- [ ] cada ~30 s relay fiscal
- [ ] cada 5 min salud del outbox fiscal
- [ ] 05:00 reconciliar documentos fiscales pendientes

Utilidades de task que hay que conservar: lock distribuido, reintento con expires, traza de steps, compensación, reporte de incidencia si la task muere. `schema_name` en el mensaje es etiqueta; en `djctoc` no cambia de base, en `djbtob` sí selecciona el schema.

---

## 14. Superficie HTTP (prefijos bajo `/api/v1/`)

Cliente

- [ ] `auth/`
- [ ] `company-roles/` `company-features/`
- [ ] `onboarding/`
- [ ] `client/inbox/`
- [ ] identidad de empresa, usuarios de empresa, filtros de módulo, grants
- [ ] conexiones, mapeos, oauth, logs de integración
- [ ] assistant chat + credentials + status
- [ ] logs (audit, ops, security, config)

Plataforma

- [ ] `platform/auth/` `platform/roles/` `platform/admin-catalog/` `platform/users/` `platform/identity/` `platform/sessions/` `platform/sections/` `platform/modules/` `platform/functionalities/`
- [ ] `companies/` y usuarios de una empresa vistos desde admin
- [ ] `billing/subscriptions/` (+ `upgrade` `cancel` `reactivate` `retry-payment` `change-status`)
- [ ] `billing/subscription-modules/` `billing/subscription-functionalities/` `billing/subscription-limits/` `billing/complements/`
- [ ] `billing/payment-methods/` `billing/invoices/` `billing/charges/` `billing/refunds/`
- [ ] `billing/webhooks/` `ecosystem/webhooks/`
- [ ] `platform/promotions/` y `promotions/` (lado empresa)
- [ ] `platform/email-senders/` `platform/email-templates/`
- [ ] `platform/policies/` y `policies/` (lectura empresa)
- [ ] `platform/locations/` `locations/` (público) `platform/currencies/` `platform/countries/`
- [ ] `platform/document-templates/`
- [ ] `platform/parameter-types/` `platform/parameters/` + el par admin
- [ ] `platform/landing-sections/` `platform/testimonials/`
- [ ] `landing/sections/` `landing/testimonials/` `subscriptions/` públicos, sin auth
- [ ] `platform/assistant-settings/` `platform/ai/model-routing/` `platform/ai/capabilities/` `platform/ai/runs/` `platform/ai/evals/`
- [ ] `platform/feature-flags/`
- [ ] `platform/integrations/catalog/` `platform/integrations/health/`
- [ ] `platform/incidents/` `platform/task-monitor/` `platform/live-logs/` `platform/support/sessions/`
- [ ] `docs/` handbook

---

## 15. Códigos de error que el catálogo ya tiene

Hay que seguir emitiendo la misma clave, el mismo HTTP y el mismo texto. Dominios:

- [ ] Auth y sesión (`AUTH_*`)
- [ ] Permisos, roles, usuarios, módulos, secciones, funcionalidades, filtros, grants
- [ ] Empresa y onboarding
- [ ] Suscripción, límites, complementos, facturas, pagos, reembolsos, promos, fiscal
- [ ] Correo, documentos, notificaciones
- [ ] Parámetros, parámetros admin, landing, testimonios, flags
- [ ] Geografía
- [ ] Políticas
- [ ] Storage, incidencias, task monitor, soporte, IA, firma, integraciones
- [ ] Handbook
- [ ] Validación genérica, rate limit, HTTP, error de servidor

Al añadir un código: inglés en el registry, español en el override, regenerar `errors.json`.

---

## 16. Operación que el producto ya espera

Comandos (o jobs equivalentes). No siembran datos de negocio en migraciones; un ensure solo crea infraestructura o filas de catálogo que el propio comando posee.

- [ ] sync de features, de códigos de módulo, de recursos compartibles, de errores i18n
- [ ] sync de monedas, de dim fecha, de dim empresa
- [ ] ensure: storage de perfiles (empresa y admin), remitente de correo, parámetros de seguridad (empresa y admin), parámetros de cierre, secciones de landing, módulo CRM, features admin del handbook
- [ ] purgas: onboarding vencido, empresas sin verificar, empresas cerradas, grants huérfanos, incidencias, retención de logs, sesiones de soporte
- [ ] vencer bonos, reparar plantilla de baja, seed del catálogo de conectores y de plantillas de promo (catálogo del producto, no filas de clientes)
- [ ] crear admin de plataforma, generar llave de producto Neurana, evals de IA
- [ ] migrar OLTP y, aparte, migrar `wadw`

Reglas que no cambian con el framework:

- [ ] Migraciones solo tocan esquema. Un backfill solo si una columna nueva `NOT NULL` se puede llenar desde otra columna de la misma fila.
- [ ] No arrancar los frontends desde el backend.
- [ ] Cupos, permisos y features se consultan; no se inventa un rol paralelo.
- [ ] Firma de webhooks y de documentos (`SIGN_*`) antes de fiarse del body.

---

## 17. Orden sugerido al portar

1. [ ] Contratos del apartado 0 (sobre, errores, cookies, validación). Sin esto los frontends no hablan.
2. [ ] Identidad cliente + admin y el gate de autorización.
3. [ ] Empresa, onboarding, suscripción y el primer cobro.
4. [ ] Factura, fiscal, reembolso, promo.
5. [ ] Correo y campanita.
6. [ ] Catálogos (geo, parámetros, landing, políticas, documentos, flags).
7. [ ] Integraciones (puerto + fake + webhook).
8. [ ] Logging y retención.
9. [ ] Incidencias, tasks, logs en vivo, chat de soporte.
10. [ ] Asistente (fake primero, SLM después).
11. [ ] Handbook.
12. [ ] Analítica.
13. [ ] Elegir bifurcación: schema por empresa (`djbtob`) o una sola base (`djctoc`). No mezclar las dos en el mismo servicio.
