# Plan de Trabajo Baja de empresa — Resumen teórico (base)

> **Propósito de este documento.** Hoja de ruta única para el **ciclo de vida de
> cierre de un tenant** (dar de baja una empresa cliente) y el tratamiento de
> **identidad de usuarios a nivel global**, alineado con el modelo B2B de
> la base y con Ley 1581 / Decreto 1377 (Colombia) y obligaciones tributarias.
> Está escrito para que cualquier colega entienda qué se construye, por qué no
> se reutiliza el toggle de suspensión, cómo se separan datos de bodega vs
> cuenta vs facturación, y qué ocurre si la empresa o una persona quieren
> volver.
>
> **Cómo se usa.** Este archivo es la parte **teórica**. Cada fase vive en
> `docs/plan-tenant-offboarding/`. Marca `[x]` solo cuando la actividad esté
> **terminada y verificada**. No marques algo a medias: déjalo `[ ]` y anótalo
> en la bitácora.
>
> **Esto no es dictamen jurídico.** El producto implementa plazos, roles
> (responsable / encargado) y evidencias. El texto de políticas, DPA y plazos
> fiscales definitivos los valida asesoría legal / tributaria.

---

## Índice

### Teoría (este archivo)

1. [Contexto y objetivo](#1-contexto-y-objetivo)
2. [Glosario](#2-glosario)
3. [Estado actual y trampas](#3-estado-actual-y-trampas)
4. [Fronteras con flujos existentes](#4-fronteras-con-flujos-existentes)
5. [Principios](#5-principios)
6. [Ciclo de vida (cierre → gracia → purga)](#6-ciclo-de-vida-cierre--gracia--purga)
7. [Identidad global y “si quieren volver”](#7-identidad-global-y-si-quieren-volver)
8. [Marco legal y dueños de cada dato](#8-marco-legal-y-dueños-de-cada-dato)
9. [Contrato, políticas y base legal de la gracia](#9-contrato-políticas-y-base-legal-de-la-gracia)
10. [Acoplamiento con otros planes](#10-acoplamiento-con-otros-planes)
11. [Mapa de fases](#11-mapa-de-fases)
12. [Bitácora de decisiones](#12-bitácora-de-decisiones)

### Fases de construcción

- [FASE 0 — Cimientos (estado de empresa, parámetros, errores)](fase-0-cimientos.md)
- [FASE 1 — Cierre y reactivación](fase-1-cierre-y-reactivacion.md)
- [FASE 2 — Export, hold y cumplimiento](fase-2-export-y-cumplimiento.md)
- [FASE 3 — Purga (tombstone, schema, MinIO, billing)](fase-3-purga.md)
- [FASE 4 — Administración plataforma (`base-admin-web`)](fase-4-admin-web.md)
- [FASE 5 — Suite de tests](fase-5-tests.md)
- [Purga: qué queda y qué se borra](purga-que-queda-y-que-se-borra.md)

---

## 1. Contexto y objetivo

**base** es un WMS SaaS multi-tenant (django-tenants: un schema
PostgreSQL por empresa). Los usuarios de cliente viven en el schema **público**
(`registration.User` / `security_users`): `username` y `email` son **únicos en
toda la plataforma** y cada usuario tiene **exactamente una** `Company` (`FK`
`PROTECT`).

Hoy el admin de plataforma puede “desactivar” una empresa, pero eso **no** es
una baja: solo voltea la última adquisición de suscripción `ACTIVE` ↔
`SUSPENDED`. El admin de la empresa sigue pudiendo entrar en modo cobro
(`billing_recovery`). Cancelar el plan y el purge de onboardings sin verificar
tampoco cubren el churn de un cliente real.

**Objetivo de este plan:** un flujo explícito de **dar de baja empresa** que:

- Cierre el acceso operativo sin confundirlo con impago.
- Trate la identidad global (email/usuario) de forma que, tras la purga, esas
  personas puedan registrarse en otra empresa.
- Permita **reactivar la misma empresa** durante una ventana de gracia.
- Tras la gracia, **devuelva/borre datos de bodega** (la base como encargado) y
  **anonimice cuentas**, conservando **facturas y evidencias de firma**.
- Deje constancia (auditoría, acta de export, certificado de borrado).

**No-objetivos:**

- No convierte `User` en membresía multi-empresa (un usuario en N tenants). Eso
  es otro proyecto.
- No implementa el canal ARCO individual (titular vs empresa aún activa). Queda
  como sibling futuro; este plan solo no debe cerrarle la puerta.
- No reescribe `ToggleCompanyActiveUseCase` para que signifique “baja”.
- No fusiona este flujo con `purge_unverified_tenants` (eso es basura de
  onboarding nunca confirmado, sin cobro asentado).
- No redacta el markdown legal de `PRIVACY-POLICY` / DPA (lo publica el módulo
  de compliance; ingeniería fija códigos, plazos técnicos y gates).
- No toca `admin_users` (mundo plataforma).

---

## 2. Glosario

| Concepto | Qué es | Dónde vive |
|----------|--------|------------|
| **Tenant / Company** | Empresa cliente; schema PostgreSQL + dominio | `platform/features/company/company/` (`companies`) |
| **Usuario cliente** | Identidad global 1:1 con una Company | `client/features/security/registration/` (`security_users`) |
| **Admin de plataforma** | operador de la base; tabla aparte | `platform/features/security/users/` (`admin_users`) |
| **Suspensión** | Impago / palanca de cobro; `CompanySubscription.status = suspended` | Billing; `AUTH_006` + `billing_recovery` |
| **Cancelación de plan** | El cliente cancela; vigencia hasta `end_date` | `CancelSubscriptionUseCase` |
| **Cierre (CLOSED)** | Baja contractual de la empresa; acceso operativo cortado | **Nuevo** estado de `Company` |
| **Gracia** | Ventana en la que el schema y las cuentas siguen existiendo para reactivar | Parámetro de plataforma + `purge_after` |
| **Purga** | Borrado operativo + tombstone de PII de cuenta; facturas se quedan | Job, mismo estilo que otros `purge_*` |
| **Tombstone** | Sustituir email/usuario/documento por valores opacos; conservar UUID | Filas `security_users` |
| **Encargado** | la base respecto de datos de bodega (instrucción del cliente) | Ley 1581; DPA |
| **Responsable** | Quien decide finalidad: la **empresa** (bodega) o **la base** (cuenta + facturación) | Ley 1581 |
| **Legal hold** | Bloqueo de purga por disputa, incidencia o requerimiento | Flag en Company |
| **Export de tenant** | Copia de datos operativos para el responsable (portabilidad / fin de encargo) | Fase 2 |
| **ARCO** | Derechos del titular (acceso, rectificación, supresión, …) | Política; **fuera** de este plan salvo no romperlos |

---

## 3. Estado actual y trampas

### 3.1 Identidad

- `username` unique global, `email` unique global.
- `User.company` obligatorio, `on_delete=PROTECT`.
- Documento único por `(company, document_type, document_number)`, no global.
- `CheckUsernameAvailabilityUseCase` / email miran **toda** la tabla: un
  email de una empresa cerrada **bloquea** el alta en otra.
- Preferencias, 2FA, dispositivos de confianza y foto (MinIO) cuelgan del
  usuario.

### 3.2 Empresa

- `Company` **no** tiene ciclo de vida propio. `is_active` en listados admin es
  `latest_sub.status == ACTIVE`.
- Schema + `Domain`; `auto_create_schema = True`.
- NIT único cuando no está vacío.

### 3.3 Lo que ya hace “algo parecido”

| Flujo | Efecto real | ¿Sirve como baja? |
|-------|-------------|-------------------|
| Toggle empresas en admin | `ACTIVE` ↔ `SUSPENDED` en la última adquisición | **No.** Abre recovery de cobro |
| Cancelar suscripción | Plan `cancelled`; login `AUTH_006` al no estar `ACTIVE` (salvo recovery si `suspended`) | Cierre de **plan**, no de tenant |
| Toggle usuario `is_active` | Cuenta inactiva; email sigue tomado | Baja de **persona** en empresa viva |
| `purge_unverified_tenants` | `DROP SCHEMA` + borra users si nadie verificó correo y no hay cobro asentado | Solo abandonos de onboarding |

Usar el toggle actual para “dar de baja” mezclaría impago con churn y dejaría
sesiones/emails en un estado indefinido.

---

## 4. Fronteras con flujos existentes

```
Login cliente
  → credenciales
  → is_active del usuario
  → email verificado
  → rol activo
  → *** NUEVO: Company.lifecycle CLOSED / PENDING_PURGE → AUTH de baja (no AUTH_006)
  → adquisición ACTIVE → full
  → adquisición SUSPENDED + admin empresa → billing_recovery
  → resto → AUTH_006
```

| Capa | Relación |
|------|----------|
| `ToggleCompanyActiveUseCase` | **Intocable** en semántica. Sigue siendo solo suspensión de plan |
| `CancelSubscriptionUseCase` | El cierre de empresa **cierra o cancela** la adquisición activa; no la pone `suspended` |
| `billing_recovery` | **No** aplica a `CLOSED`. El cliente que se fue no entra a “pagar para volver” por esa vía; vuelve con `ReopenCompany` |
| `purge_unverified_tenants` | Job **distinto**; filtro: nunca verified + sin cobro. No debe seleccionar `CLOSED` |
| `core/access` cupos | Al cerrar, dejar de contar usuarios activos para cupo; al reabrir, reconcilia |
| Compliance (`PRIVACY-POLICY`, `TERMS-AND-CONDITIONS`, firmas append-only) | Base contractual; DPA/`DATA-PROCESSING` se suma en Fase 2 |
| Incidencias (`platform/features/support/incident`) | Hold si hay incidencia abierta del tenant |
| Storage MinIO | Prefijo tenant se borra **en purga**, no en cierre |
| `admin_users` | Fuera de alcance |

---

## 5. Principios

1. **Tres tratamientos, tres destinos.** Bodega se exporta y se borra; cuenta se
   anonimiza; factura se conserva.
2. **Reversible en gracia, irreversible en purga.** No hay restore del schema
   después del `DROP`.
3. **No borrar UUID de usuario.** Auditoría, firmas (`subject_id`), testimonios
   `DO_NOTHING` necesitan la fila tombstone.
4. **No reutilizar `SUSPENDED`.** Impago ≠ baja.
5. **La gracia solo existe si el contrato/política la anuncian.** Conservar el
   schema “por si acaso” sin cláusula es finalidad opaca (caducidad, Decreto 1377).
6. **Un use case = una responsabilidad.** `CloseCompany`, `ReopenCompany`,
   `ExportTenant`, `PurgeClosedCompany` separados. Presentation valida con
   `RequestBody`; dominio Pydantic; errores `ERROR_REGISTRY`.
7. **Best-effort de infra, atómico de negocio.** Revocar Redis/sesiones no debe
   dejar la empresa “a medias” si falla MinIO; la purga de schema sí es el
   punto de no retorno y va transaccionada con tombstone + liberación de NIT
   en el orden que no deje FKs `PROTECT` huérfanos.
8. **Migraciones solo esquema.** Seeds de políticas/plazos: management command o
   CMS de compliance, nunca `RunPython` de catálogo.
9. **Copy de operario / admin.** Sin UUID en mensajes al usuario de plataforma;
   códigos internos sí en envelope.

---

## 6. Ciclo de vida (cierre → gracia → purga)

Estados de **empresa** (campo nuevo; no confundir con `CompanySubscription.status`):

```
ACTIVE ──CloseCompany──► CLOSED ──(purge_after)──► PENDING_PURGE ──job──► (fila residual / GONE)
              ▲                    │
              └──── ReopenCompany ─┘   (solo CLOSED, dentro de gracia, sin hold)
```

`PENDING_PURGE` es el instante en que el job tomó el tenant (o el admin forzó
purga); evita doble drop.

### 6.1 Cierre (`CloseCompany`)

Actor: admin de plataforma (MVP). Más adelante se puede ofrecer al admin de
empresa como autoservicio; no es Fase 1.

Efectos:

- `lifecycle = CLOSED`, `closed_at = now()`, `purge_after = closed_at + gracia`.
- Motivo y actor auditados.
- Adquisición activa → `cancelled` o `closed` (nunca `suspended`).
- Todos los usuarios de esa company: `is_active = False` (respetar los que ya
  lo estaban: no hace falta flag extra si al reabrir solo se reactivan los
  desactivados **por este cierre** — ver Fase 1, campo `deactivated_by_company_close`).
- Revocar refresh/sesiones de todos esos usuarios.
- Login: credenciales pueden ser correctas; respuesta de **empresa dada de baja**,
  código nuevo (p. ej. `AUTH_019`), distinto de `AUTH_006` y `AUTH_003`.
- Schema, MinIO, NIT, dominio: **intactos**.
- Disparar export (Fase 2) o exigir constancia de “export entregado / renuncia”.

### 6.2 Gracia

- Default sugerido: **90 días**, parámetro de plataforma (no hardcode).
- Nadie opera el WMS. Emails/usuarios siguen ocupados (así se puede reactivar).
- Admin plataforma ve reloj y acciones: Reactivar / Purga anticipada (con
  confirmación fuerte + hold check).

### 6.3 Reactivación (`ReopenCompany`)

- Solo `CLOSED`, `now < purge_after`, sin legal hold.
- `lifecycle = ACTIVE`, limpia `closed_at` / `purge_after`.
- Nueva adquisición o reactivar plan según reglas de billing (Fase 1 concreta
  el acoplamiento: no inventar cobro mágico).
- Reactivar usuarios marcados por el cierre; no reactivar bajas individuales
  previas.
- Mismo schema, mismo inventario, mismas contraseñas.

### 6.4 Purga (`PurgeClosedCompany`)

Job periódico (Celery + `manage.py`), idempotente, **un tenant por transacción**.

No corre si: `legal_hold`, cobro/incidencia en disputa, o `lifecycle != CLOSED`
con `purge_after` aún futura (salvo purga forzada auditada).

Orden conceptual:

1. Constancia de export (o renuncia) persistida.
2. Tombstone de usuarios: email/username/teléfono/documento/foto/password;
   borrar 2FA, trusted devices, recovery tokens, preferencias no necesarias.
3. Liberar NIT (vaciar o sufijo documental **sin** violar unique si se conserva
   histórico comercial en otra tabla; recomendación: `nit` vacío + NIT
   histórico en registro de cierre).
4. Borrar prefijo MinIO del tenant.
5. `company.delete(force_drop=True)` o equivalente django-tenants (`DROP SCHEMA`).
6. Conservar `Charge` / `Invoice` / firmas de políticas (FKs a Company: ver
   Fase 3 — billing ya usa `CASCADE` en adquisiciones; hay que **desacoplar**
   evidencia fiscal de la fila `companies` o materializar un snapshot).
7. Certificado de borrado (log + fila de evidencia, no un PDF obligatorio en MVP).

**Punto de diseño abierto (Fase 0/3):** hoy `Invoice`/`Charge` apuntan a
`Company`. No se puede `DROP` la empresa y “conservar facturas” si el FK se
cae. El plan exige un **ancla fiscal** (snapshot `company_id` + `nit` + `name`
en el documento de cobro, y FK `SET_NULL` o tabla `ClosedTenantRecord` en
`public`). Eso se resuelve en Fase 0 (modelo) y se ejecuta en Fase 3.

---

## 7. Identidad global y “si quieren volver”

Tres casos de producto, tres tratamientos:

| Quién vuelve | Cuándo | Qué pasa |
|--------------|--------|----------|
| **Misma empresa** | Dentro de la gracia | `ReopenCompany`. Mismos usuarios, mismo schema |
| **Misma empresa** | Después de la purga | Onboarding nuevo. NIT y correos ya libres. Datos de bodega no se recuperan (salvo el export) |
| **Una persona** (operario) en **otra** empresa de la base | Tras tombstone | Alta nueva en el otro tenant. No hereda roles ni UUID operativo. Mientras la primera empresa esté en gracia, el email **sigue tomado** |

Limitación consciente del modelo 1:1: no se puede “traspasar” al operario a
otra bodega el día del cierre sin tombstone anticipado (haría irreversible la
reactivación de la primera empresa). No se hace en este plan.

Admin de plataforma: irrelevante; no comparte tabla.

---

## 8. Marco legal y dueños de cada dato

Referencia de producto (Colombia). Otros países: misma **separación de
tratamientos**; plazos vía `PolicyCountry`.

Ley 1581 protege **datos de personas naturales**. Razón social / NIT de una SAS
no son dato personal. Nombre, email y cédula del admin u operario sí lo son.
Datos de destinatarios en pedidos son del **cliente** (responsable); la base es
**encargado**.

### 8.1 Matriz de destino

| Bloque | Titular / sujeto | Rol de la base | Cierre | Gracia | Purga |
|--------|------------------|-------------|--------|--------|-------|
| Schema WMS, MinIO tenant, logs de piso | Empresa (responsable de bodega) | Encargado | Bloquear + export | Conservar **solo** si la política lo dice | Borrar / drop |
| Cuenta (email, usuario, cédula, foto) | Persona; la base responsable de la cuenta | Responsable (cuenta) | Desactivar, no borrar | Conservar para reactivar si está pactado | Tombstone; liberar identificadores |
| Firmas de políticas | Evidencia de autorización | Conservar prueba | Conservar | Conservar | Conservar sello; PII del firmante minimizable |
| Facturas, cargos | Relación comercial + deber fiscal | Responsable (billing) | Conservar | Conservar | **No borrar** (orden de magnitud: 10 años, C. Co. art. 60 / DIAN) |
| Sesiones, tokens, 2FA | Seguridad del servicio | — | Revocar ya | — | — |

El derecho de supresión **no es absoluto** (contrato, ley, proceso, defensa).
`legal_hold` cubre incidencia abierta, disputa de cobro o requerimiento.

### 8.2 Empresa vs titular (no mezclar en un botón)

- **Baja de empresa:** el cliente, como responsable de la bodega, instruye al
  encargado. No se espera el OK de cada operario.
- **ARCO de un operario con empresa viva:** el titular pide a su empleador; la
  empresa puede pedir a la base desactivar la **cuenta**. la base no vacía el
  historial de picking por esa vía. **Fuera de este plan.**
- **Empresa ya purgada y la persona quiere su correo:** el tombstone es el
  cumplimiento (caducidad / finalidad agotada).

### 8.3 Regla corta

**La bodega se devuelve y se borra; la cuenta se anonimiza; la factura se
conserva.** Mezclar las tres es el riesgo legal y de producto.

---

## 9. Contrato, políticas y base legal de la gracia

El onboarding **ya** sella `PRIVACY-POLICY` y `TERMS-AND-CONDITIONS` por país
(`core.signing`, `PolicySignature` append-only). Sin texto que describa el
cierre, la gracia y la purga, el software haría un tratamiento no informado.

Ingeniería **no** redacta el dictamen; sí:

1. Lista de cláusulas mínimas que legal debe publicar (abajo).
2. Código de política `DATA-PROCESSING` (DPA / encargo) en el catálogo;
   firma en finalize o en un paso admin-empresa, según decida compliance.
3. Que el parámetro de días de gracia coincida con lo publicado (o sea un
   máximo: el job usa `min(parametro, lo_firmado)` si se versiona; MVP: un
   parámetro global alineado al texto CO).

**Privacidad (CO y cada `PolicyCountry`):**

- la base encargado de datos de bodega; responsable de cuenta y facturación.
- Plazos: gracia, logs, facturas, firmas.
- Export al salir.
- Canal ARCO (empresa vs persona).
- Liberación de email tras purga.

**Términos:**

- Baja ≠ suspensión por impago.
- Quién puede pedirla (MVP: plataforma).
- Export o renuncia antes de purgar.
- No hay restore del schema post-purga.

**DPA / encargo:**

- Instrucciones del cliente.
- Subencargados (MinIO, email, pasarela).
- Plazo máximo de borrado tras fin del encargo.
- Certificado de borrado.

---

## 10. Acoplamiento con otros planes

| Plan / módulo | Acoplamiento |
|---------------|--------------|
| Billing / suscripciones | Cierre no usa `suspended`; facturas sobreviven a la empresa |
| Onboarding + `purge_unverified_tenants` | Jobs y criterios disjuntos |
| Compliance / policies | Textos + DPA; firmas no se borran en purga |
| Incidencias | `legal_hold` |
| Integraciones (`plan-integrations`) | Al cerrar: desactivar conexiones; en purga: secretos tenant |
| IA (`plan-ia`) | No reentrenar ni retener prompts de un tenant CLOSED más allá de logs ya retenidos |
| Logging retention | Logs de piso se van con el tenant o con `run_log_retention`; no mezclar con facturas |
| `base-admin-web` | Acción explícita, distinta del toggle actual |
| `base-client-web` | MVP: mensaje de login; autoservicio de baja **no** es Fase 4 |

---

## 11. Mapa de fases

| Fase | Entregable principal | Repo(s) |
|------|----------------------|---------|
| **0** | Estado de empresa, parámetros de gracia, errores, ancla fiscal (diseño de FK) | base |
| **1** | `CloseCompany` / `ReopenCompany`, sesiones, usuarios, login, billing | base |
| **2** | Export, hold, constancias, gates de políticas/DPA | base |
| **3** | Job de purga, tombstone, MinIO, drop schema, certificado | base |
| **4** | UI admin: dar de baja / reactivar / ver reloj (sin reusar el toggle) | base-admin-web |
| **5** | Matriz de tests unitarios / API | base |

Orden: 0 → 1 → 2 y 5 en paralelo cuando 1 esté estable → 3 depende de 0+2
(export/hold) → 4 puede arrancar en cuanto existan los POST de 1 (UI mínima) y
completarse con 2–3.

---

## 12. Bitácora de decisiones

| Fecha | Decisión |
|-------|----------|
| 2026-09-15 | Baja de empresa es ciclo CLOSED → gracia → purga; no el toggle `SUSPENDED` |
| 2026-09-15 | Usuarios globales 1:1 se desactivan en cierre y se tombstonean en purga (no se borran UUID) |
| 2026-09-15 | Tres destinos: bodega export+borrado; cuenta anonimizada; facturas retenidas |
| 2026-09-15 | Reactivar = misma empresa en gracia; post-purga = onboarding nuevo |
| 2026-09-15 | Persona en otra empresa de la base solo tras tombstone; no multi-membresía en este plan |
| 2026-09-15 | Gracia por defecto 30 días (parámetro `DAYS_COMP_DEREGISTRA`); debe constar en política/términos |
| 2026-09-15 | `purge_unverified_tenants` permanece aparte |
| 2026-09-15 | ARCO individual con empresa viva queda fuera de alcance |
| 2026-09-15 | Actor MVP del cierre: admin de plataforma |
| 2026-09-15 | Ancla fiscal opción 1: `ClosedTenantRecord` + snapshot `tenant_nit`/`tenant_name` en Invoice y Charge. El FK a Company se anula en la purga (Fase 3). Gracia vía parámetro `DAYS_COMP_DEREGISTRA` (30). |
| 2026-09-15 | `DAYS_COMP_DEREGISTRA = 0`: baja inmediata (cierre + export + purga en el mismo POST). No requiere el job. Valor negativo se rechaza. |
| 2026-09-15 | Listados operativos de empresas y usuarios ocultan `GONE` (tombstones). `CLOSED` sigue visible en gracia. Detalle en [purga-que-queda-y-que-se-borra.md](purga-que-queda-y-que-se-borra.md). |
