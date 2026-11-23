<p align="center">
  <img width="800" height="215" alt="image" src="https://github.com/user-attachments/assets/a1f4353f-36e7-4341-b009-b1c06d67adfc" />
</p>

Sistema **SaaS multi-tenant** listo para construir un producto encima: schema PostgreSQL por empresa, billing, auth, RBAC y observabilidad. El dominio de negocio del tenant entra como un L2 nuevo bajo `client/features/`.

> ⚙️ Proyecto enfocado en arquitectura robusta, procesamiento eficiente y escalabilidad.

---

## 🏢 Dos mundos: platform y client

Este repo es **la base** que venden muchas empresas. Cada empresa es un
**tenant**: tiene su propio schema y sus propios usuarios. Lo que **no**
comparte con la vecina son los datos de su operación. Lo que **sí** comparte
es la plataforma: planes, facturas, catálogo de features y el equipo que
administra el SaaS. El dominio de negocio (lo que esa operación hace) no viene
en el template: se agrega como feature L2.

Eso se traduce en dos carpetas y dos “mundos” de datos:

| | **Platform** (`platform/`) | **Client** (`client/`) |
|---|---|---|
| **Quién lo usa** | El equipo de la base (portal admin) | La empresa cliente (portal del producto) |
| **UI** | `admin.base.local` | `app.base.local` |
| **Pregunta de negocio** | ¿Quién paga, qué plan tiene, está activa? | ¿Quién entra, qué puede hacer, qué pasó? |
| **Ejemplos** | Empresas, planes, facturas, promociones, flags, catálogo de conectores, incidencias | Usuarios de empresa, roles, inbox, asistente, conexiones, logs |
| **Dónde viven los datos** | Schema PostgreSQL `public` (compartido) | Un schema **por empresa** (`mattelsa`, `arisoft-sas`, …) |

`core/` no es un tercer mundo: son utilidades transversales (errores, auth,
validadores, IA, integraciones) que **los dos** pueden usar. No pongas ahí
reglas del producto ni de facturación.

### Por qué un schema por empresa

No es un capricho técnico. El invariante de negocio es:

> Los datos de **una** empresa no pueden mezclarse nunca con los de **otra**.
> Ni por un `JOIN` despistado, ni por un listado sin filtro, ni por un job de
> Celery que “se olvidó” de la empresa.

PostgreSQL schemas son el aislamiento: cada tenant es un namespace de tablas
dentro de la misma base. Misma app Django, mismas migraciones del cascarón,
datos físicamente aparte. Si mañana se va una empresa, se puede tirar **su** schema
sin tocar el de las demás ni el `public`.

El `public` guarda lo que es de **la base como producto**:

- El padrón de empresas (`Company`) y sus dominios (`Domain`).
- Billing: planes, suscripciones, cobros, reembolsos, promociones.
- Usuarios admin de plataforma (`AdminUser`) y el catálogo de módulos/features.
- Usuarios de empresa (`User`): viven en `public` **pero** cada uno apunta a
  **una** `Company`. No se copian al schema del tenant.
- Onboarding (el alta todavía no tiene schema de operación).

El schema de la empresa guarda lo que es de **esa operación**: inbox,
historial del asistente, logs, conexiones de integración, filtros y accesos
por entidad. Las tablas del producto se agregan aquí cuando exista el dominio.

### Cómo nace una empresa

Da igual si el alta la hace el admin de plataforma o el wizard de onboarding:
el desenlace es el mismo.

1. Del nombre comercial se deriva un identificador seguro para Postgres
   (`Mattelsa` → `mattelsa`, `Ari Soft SAS` → `ari-soft-sas`).
2. Se crea la fila `Company` en `public` (NIT, dirección, plan).
3. Se crea un `Domain` `mattelsa.base.local` (en prod,
   `mattelsa.<dominio>`). Eso es lo que usa django-tenants para saber **quién**
   es la petición.
4. Django crea el schema PostgreSQL (`auto_create_schema`) y corre las
   migraciones del tenant **solo** en ese schema.
5. Queda un usuario administrador de **esa** empresa, ligado a la `Company`,
   con la suscripción activa.

Hasta que eso no termina, no hay schema de operación. Por eso el onboarding y el catálogo
de planes viven en `public`: todavía no existe el schema del cliente.

### Cómo una petición sabe en qué mundo está

El middleware de django-tenants mira el **Host**:

```
http://admin.base.local:4120     →  schema public   →  portal admin
http://app.base.local:4110       →  schema public   →  SPA del cliente
http://mattelsa.base.local:8100  →  schema mattelsa →  APIs del tenant
```

- Si el Host **no** es el de una empresa (`app.`, `admin.`, la landing), se
  usa el schema `public` y las rutas “públicas” (`base/urls_public.py`): login,
  onboarding, catálogo, billing de plataforma, campanita, etc.
- Si el Host **sí** es `{empresa}.base.local`, se usa el schema de esa
  empresa y las rutas de tenant (`base/urls.py`): identidad, integraciones,
  asistente, logs.

La SPA del cliente **no cambia de subdominio** (siempre `app.base.local`).
La cookie de sesión cubre todo `.base.local`, así el browser puede hablar
con el backend en el host de la empresa cuando hace falta. Hay pantallas
(campanita, settings de compañía) que siguen pegándole a `app.base.local`
y el backend entra al schema correcto **porque el usuario del JWT ya pertenece
a una sola empresa**. Dos caminos, misma regla: los datos del tenant nunca se
leen “a ciegas” en `public`.

Hay **dos tipos de persona**, con cookies distintas (`access_admin` /
`access_client`) y el header `X-Auth-Context` para no confundirlas si ambas
sesiónes están abiertas en el mismo browser:

| Persona | Tabla | Qué puede hacer |
|---|---|---|
| Admin de plataforma | `admin_users` | Crear empresas, planes, ver facturación, flags, incidencias |
| Usuario de empresa | `security_users` | Opera **su** tenant; `IsCompanyMember` lo ata a su `Company` |

Un admin de plataforma **no** es usuario de una empresa cliente. Un usuario de
empresa **no** ve el billing global ni los datos de otra empresa.

### Lógica que hay que respetar al programar

- **¿Es del tenant (usuarios, inbox, logs, el producto que construyas)?** →
  `client/features/…` y tablas en `TENANT_APPS`. El use case asume que ya
  estás dentro del schema de esa empresa.
- **¿Es del SaaS (plata, plan, alta de empresa, catálogo global)?** →
  `platform/features/…` y tablas en `SHARED_APPS` (`public`).
- **No cruces los cables.** Una factura no se guarda en el schema del tenant.
  Un dato de la operación no se guarda en `public`. Si un job de Celery toca
  el schema de una empresa, tiene que recibir `schema_name` y entrar con
  `schema_context`; si no, está escribiendo en el schema equivocado (o en
  `public`).
- **Migraciones:** `migrate` solo toca `public`. Los schemas de las empresas
  se actualizan con `python manage.py migrate_schemas`. Una tabla nueva del
  tenant que no migras a las empresas **no existe** para esas empresas.
- **En producción** el DNS real resuelve `{empresa}.base…`. En tu PC hace
  falta el comodín local (sección de dominios más abajo); no es un requisito
  del producto en la nube.

```
                    ┌─ public ─────────────────────────┐
  Admin de la base ──► │ empresas, planes, facturas,      │
                    │ usuarios, onboarding              │
                    └──────────────┬────────────────────┘
                                   │ nace Company + Domain
                                   ▼
                    ┌─ mattelsa ───┐  ┌─ arisoft-sas ─┐
  Operario     ──►  │ su operación │  │ su operación  │  ← aislados
                    └──────────────┘  └───────────────┘
```

Hay un tercer mundo de producto: **`handbook/`** (documentación de
plataforma en schema `public`). Junto con `platform/` y `client/` forma el
**Nivel 1** de la jerarquía de features.

---

## 🧱 Jerarquía de features (4 niveles)

Toda lógica de negocio bajo `client/features/`, `platform/features/` y
`handbook/features/` se organiza en **cuatro niveles**. Ese es el estándar de
construcción del monolito: facilita extraer un módulo a microservicio sin
arrastrar entidades mal ubicadas, y fija **dónde** aplica Clean Architecture.

| Nivel | Nombre | Qué es | ¿Clean Architecture? | Ejemplo |
|------:|--------|--------|----------------------|---------|
| **1** | Mundo | Fuente de información / bounded context de despliegue | No | `client`, `platform`, `handbook` |
| **2** | Feature | Conjunto de lógicas **desacoplado**, candidato a MS | **No** | `client/features/security` |
| **3** | Lógica conjunta | Familia / subdominio de la misma entidad | **No** | `security/access` |
| **4** | Entidad | Lógica específica de una entidad | **Sí** | `security/access/roles` |

### Forma canónica

```text
{mundo}/features/{feature-L2}/{logica-conjunta-L3}/{entidad-L4}/
  domain/
  application/
  infrastructure/
  presentation/
  migrations/    # si aplica
  models.py      # si aplica
```

**Referencia correcta en el repo:**
`client/features/security/access/roles`.

### Reglas

1. **L1** solo agrupa mundos (`client` | `platform` | `handbook`).
2. **L2** es la frontera de extracción a microservicio. **Sin** `domain/` ni
   capas CA. Solo contiene L3 (y helpers sin CA: `facade`, `common`, …).
3. **L3** agrupa entidades hermanas. **Sin** CA. Obligatorio si hay ≥2
   entidades de la misma familia.
4. **L4** es el **único** nivel con distribución hexagonal
   (`domain` → `application` → `infrastructure` → `presentation`).
5. Una **lógica única** no es L2. Si solo hay una entidad (p. ej. un chat),
   es L4 bajo un L2 real — no pongas CA en la raíz del feature.
6. `core/` no es un mundo L1 de features: son utilidades transversales
   (errores, validadores, IA, storage). No coloques ahí entidades del producto
   ni de billing.

```text
# ✅ L2 = conjunto extractable; CA solo en L4
client/features/security/            # L2 — sin CA
  access/                            # L3 — sin CA
    roles/                           # L4 — con CA
      domain/ application/ infrastructure/ presentation/

# ❌ Entidad elevada a L2 (no es un conjunto de lógicas)
client/features/assistant/           # CA aquí = mal
  domain/ application/ …

# ❌ CA en L2 y además en un hijo
client/features/integrations/        # CA + hijos
  oauth/                             # también CA
```

Auditoría del estado actual y plan de remediación:

- [`docs/features-hierarchy-audit.md`](docs/features-hierarchy-audit.md)
- [`docs/features-hierarchy-remediation-plan.md`](docs/features-hierarchy-remediation-plan.md)

---

## 📦 Instalación

### 🔹 1. Crear entorno virtual
```bash
python -m venv venv
# o
python3 -m venv venv
```

### 🔹 2. Activar entorno virtual
```bash
# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 🔹 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

> 💡 Asegúrate de ver `(venv)` en tu terminal antes de instalar.

---

## ⚙️ Configuración

### 🔹 1. Bases de datos

El stack Docker levanta **dos** databases en el mismo Postgres:

| Alias Django | Database física | Rol |
|---|---|---|
| `default` | `wadb` (o `DB_NAME`) | OLTP multi-tenant |
| `analytics` | `wadw` (o `DW_NAME`) | Data Warehouse (ETL) |

En un **volumen nuevo**, el script `docker/postgres/init-wadw.sh` crea `wadw`
al inicializar Postgres. Si el volumen ya existía (caso habitual en dev):

```bash
docker compose up -d postgres
docker exec -it wa-postgres \
  psql -U wa_user -d postgres -c "CREATE DATABASE wadw;"
```

(Si ya existe, Postgres responde que la DB existe — OK.)

Verificar:

```bash
docker exec -it wa-postgres psql -U wa_user -d postgres -c "\l" | grep wadw
python manage.py shell -c "from django.db import connections; connections['analytics'].ensure_connection(); print('analytics ok')"
```

Migraciones dimensionales van con::

```bash
python manage.py migrate_analytics
python manage.py load_dim_date --from 2024-01-01 --to 2030-12-31
python manage.py sync_dim_company
```

(`migrate --database=analytics` no sirve: django-tenants intercepta `migrate`
y espera el backend multi-schema.) **No** uses el backend `django_tenants`
en el alias `analytics`.

Detalle: `docs/plan-datawarehouse/`.

### 🔹 2. Variables de entorno
- Copia `base/settings/.env.ex` → `base/settings/.env`
- Configura credenciales OLTP (`DB_*`). El DW reutiliza host/user/password
  vía defaults; opcionalmente sobrescribe con `DW_*` (prod: instancia aparte).

### 🔹 3. Migraciones
```bash
python manage.py makemigrations
python manage.py migrate_schemas
```

> `migrate` solo actualiza el schema `public`. `migrate_schemas` aplica también
> las tablas del tenant en **cada** empresa. En un clone fresco, usa este último.

### 🔹 4. Ejecutar servidor
```bash
python manage.py runserver 8100
```

---

## 🏠 Dominios locales (solo en tu PC)

En local cada empresa vive en un subdominio: `arisoft-sas.base.local`,
`mattelsa.base.local`, etc. (es el `Domain` que se crea al dar de alta la
compañía; ver [Dos mundos](#-dos-mundos-platform-y-client)). El cliente queda
en `app.base.local`, el admin en `admin.base.local` y la landing en
`base.local`.

**En producción no tienes que hacer nada de esto.** Ahí el DNS real ya apunta
los subdominios al servidor. Esta guía es solo para que tu Windows entienda
`*.base.local` sin ir al archivo `hosts` cada vez que nace una empresa.

### Por qué no usar el archivo `hosts`

Windows no acepta comodines ahí. Tendrías que escribir a mano una línea por
empresa, y se te va a olvidar. En su lugar usamos **Acrylic DNS Proxy**: un
ayudante local que dice “todo lo que termine en `.base.local` soy yo,
127.0.0.1”. El resto de internet (Google, etc.) lo deja pasar igual.

### 1. Instalar Acrylic

1. Descárgalo desde la [página de Acrylic](https://mayakron.altervista.org/support/acrylic/Home.htm).
2. Instálalo con permisos de administrador y deja el servicio corriendo.

### 2. Una sola regla para todos los subdominios

Abre `C:\Program Files (x86)\Acrylic DNS Proxy\AcrylicHosts.txt` (también
está en el menú de Acrylic → *Open Acrylic Hosts*) y deja al final:

```
127.0.0.1 >base.local
```

Esa línea cubre `base.local` **y** cualquier cosa `*.base.local`.
Guarda el archivo. Más adelante vamos a reiniciar el servicio.

> El símbolo `>` no es un error: es el atajo de Acrylic para “este nombre y
> todos los que cuelgan de él”.

### 3. Decirle a Windows que pregunte a Acrylic

En **Configuración → Red e Internet → Wi-Fi → tu red → Asignación de servidor DNS → Manual**:

| | Valor |
|---|---|
| IPv4 preferido | `127.0.0.1` |
| IPv6 preferido | `::1` |
| DNS sobre HTTPS | **Desactivado** |

Si lo dejas en “solo cifrado”, Windows habla con Google/Cloudflare y se salta
a Acrylic. En Chrome revisa también `chrome://settings/security` y apaga
**Usar DNS seguro**.

O desde una consola **como administrador**, **una línea a la vez** (si las pegas
todas juntas, Windows las junta en un solo comando y falla):

```bat
netsh interface ipv4 set dnsservers name="Wi-Fi" static 127.0.0.1 primary
netsh interface ipv6 set dnsservers name="Wi-Fi" static ::1 primary
ipconfig /flushdns
```

Si tu red no se llama `Wi-Fi`, mira el nombre con `netsh interface show interface`.

### 4. Cómo saber que ya funciona

```bat
nslookup nueva-empresa.base.local 127.0.0.1
nslookup google.com 127.0.0.1
nslookup nueva-empresa.base.local
```

Lo esperado: la empresa inventada responde `127.0.0.1`, Google responde con
una IP real, y el tercer comando usa el servidor `127.0.0.1` (ya no el del
router). En el navegador prueba un host que **nunca** hayas puesto en `hosts`,
por ejemplo `http://nueva-empresa.base.local:8100`.

### 5. Limpia el `hosts` de Windows

Cuando Acrylic ya responda, quita del archivo
`C:\Windows\System32\drivers\etc\hosts` todas las líneas `# base`
(`app.base.local`, empresas, etc.). **No borres** las de Docker Desktop
(`host.docker.internal`, `gateway.docker.internal`, `kubernetes.docker.internal`):
Docker las reescribe solo y no son `*.base.local`.

Luego otra vez `ipconfig /flushdns`.

---

### Cosas a las que hay que prestar atención

**Pega los comandos de a uno.** Si los juntas en una sola línea, `net stop`
se come el resto y acaba quejándose de `/FLUSHDNS` u otras opciones que no
existen.

**Windows a veces “ocupa la puerta” del DNS.** Si `nslookup … 127.0.0.1`
dice *No response from server*, casi seguro **Internet Connection Sharing
(ICS)** se quedó con el puerto 53. Suele arrancarlo **Host Network Service**
(lo usan WSL y Docker). Acrylic queda sordo en IPv4 aunque el servicio esté
verde.

**No deshabilites Host Network Service para siempre.** WSL/Docker lo necesitan.
La idea es: pararlo un momento, soltar ICS, dar el puerto a Acrylic, y
volver a encender HNS. ICS puede quedar corriendo *después*; lo importante
es que Acrylic haya llegado primero al puerto.

Si te pasa, consola **como administrador**, una línea y Enter cada vez:

```bat
sc config hns start= disabled
net stop hns
net stop SharedAccess
net stop AcrylicDNSProxySvc
net start AcrylicDNSProxySvc
sc config hns start= demand
net start hns
netsh interface ipv4 set dnsservers name="Wi-Fi" static 127.0.0.1 primary
ipconfig /flushdns
nslookup nueva-empresa.base.local 127.0.0.1
```

`sc config hns start= disabled` es **temporal**, para que HNS no se rearranque
solo entre el `net stop hns` y el `net stop SharedAccess`. El `start= demand`
lo deja otra vez en manual. Si te saltas ICS y vas directo a `net start hns`,
HNS vuelve a levantar ICS y seguimos igual.

Tras un reboot, para que ICS no gane la carrera al arrancar:

```bat
sc config SharedAccess start= disabled
```

**Si dejas de navegar a internet** justo después de poner DNS `127.0.0.1`,
Acrylic no está contestando. Vuelve el DNS del router y respira:

```bat
netsh interface ipv4 set dnsservers name="Wi-Fi" dhcp
```

Luego repite el baile de HNS → ICS → Acrylic.

**Otra red Wi-Fi puede olvidar a Acrylic** y volver al DNS del router. Vuelve
a poner `127.0.0.1` / `::1` en esa red.

**El icono de red a veces dice “sin Internet”** aunque todo ande. Es un
falso positivo conocido de Acrylic; si `nslookup google.com` funciona, estás
bien.

**Después de tocar `AcrylicHosts.txt`** hay que reiniciar el servicio Acrylic
(menú de Acrylic o `net stop` / `net start AcrylicDNSProxySvc`). Si no, sigue
usando la versión anterior en memoria.

---

## 🧪 Tests

### 🔹 Unitarios
```bash
pytest
```

### 🔹 Integración
```bash
docker compose up -d postgres redis
pytest -m integration
```

💡 Tips:
- Usa `--reuse-db` para acelerar ejecuciones
- Los schemas de test se limpian automáticamente

---

## 🤖 IA / SLM nativo (assistant — Fase 0b)

La **lógica de IA** vive en `core/ai/` dentro de este repo. El **runtime de
inferencia** (Ollama) es un contenedor **opcional**: si no lo levantás, no
consume RAM/CPU del modelo.

| Pieza | Rol |
|---|---|
| `core/ai/` (`AI_PROVIDER=local`) | Adaptador HTTP → runtime |
| `ai-runtime` (compose profile `ai`) | Carga el SLM y genera tokens |
| `AI_ENABLED=false` | Kill-switch de producto (no llama al runtime) |
| Sin profile `ai` | Kill-switch de infra (~0 RAM del modelo) |

### Encender (dev)

```bash
# Stack base (sin IA)
docker compose up -d postgres redis minio

# Runtime SLM (opcional)
docker compose --profile ai up -d
docker compose --profile ai exec ai-runtime ollama pull qwen2.5:1.5b
```

En `.env` (`base/settings/.env`):

```env
AI_ENABLED=true
AI_PROVIDER=local
AI_RUNTIME_URL=http://127.0.0.1:3310
AI_CHAT_MODEL=qwen2.5:1.5b
AI_MAX_CONCURRENT=1
```

### Smoke test

```bash
python manage.py shell -c "from core.ai import get_chat_model, Prompt, Message; c=get_chat_model('local').complete(Prompt(messages=[Message.user('Di hola en una palabra')])); print(c.provider, c.model, c.text)"
```

### Apagar (liberar RAM)

```bash
docker compose --profile ai stop ai-runtime
# o: docker compose --profile ai down
```

Footprint orientativo (CPU, `qwen2.5:1.5b` Q4): ~2–3 GB RAM idle con el
modelo cargado; cold start de segundos al primer request tras pull. Sin GPU en
MVP. Detalle: `docs/plan-ia/fase-0b-runtime-slm.md`.

### assistant (Fase 3)

API tenant (JWT + membership):

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/v1/assistant/status/` | ¿IA habilitada? |
| POST | `/api/v1/assistant/chat/` | `{ message, conversation_id? }` |
| GET | `/api/v1/assistant/conversations/` | Historial |
| WS | `/ws/assistant/` | Stream: thinking → tool → typing → token* → done |

Cliente WS: cookie JWT (mismo origen). Payload de entrada:
`{"type":"assistant.chat","payload":{"message":"...","conversation_id":null}}`.

Migrar schemas tras pull: `python manage.py migrate_schemas`.

---

## ⚡ Tareas automatizadas (Celery + Redis)

`python manage.py runserver 8100` **solo** atiende HTTP/WebSocket. Las tareas
programadas (purgas, renovaciones, demo del monitor, etc.) las dispara
**Beat** y las ejecuta un **Worker**, con **Redis** como cola.

### 🔹 Qué debe estar corriendo

| Pieza | Comando | Rol |
|---|---|---|
| Infra | `docker compose up -d postgres redis minio` | DB + broker Redis + storage |
| API | `python manage.py runserver 8100` | HTTP / admin / WebSocket |
| Worker | `python manage.py runworkers` | Ejecuta las tareas encoladas |
| Beat | `python manage.py runbeat` | Encola a la hora programada |

Sin Beat → nadie encola. Sin Worker → se encola pero no corre. Sin Redis →
falla cualquiera de los dos. Las cuatro piezas deben quedar vivas en
terminales separadas (si reiniciás Redis, volvé a lanzar worker y beat).

### 🔹 Pre-requisitos

```bash
docker compose up -d redis
```

En `.env` (opcional; hay defaults locales):

- `CELERY_BROKER_URL` (Redis DB 2)
- `CELERY_REDBEAT_REDIS_URL` (Redis DB 3)
- `TASK_MONITOR_DEMO_ENABLED` — en `local` el default es `true` (probe cada 2 min)

### 🔹 Arranque local

Desde la raíz de `base`, con el venv activo:

```bash
# Terminal 1 — API
python manage.py runserver 8100

# Terminal 2 — Worker
python manage.py runworkers

# Terminal 3 — Beat (scheduler)
python manage.py runbeat
```

`manage.py` ya fija `DJANGO_SETTINGS_MODULE=base.settings.local`; no hace falta
exportar `PYTHONPATH` ni settings a mano.

> **Nombre del worker:** se usa `runworkers` (plural) porque `runworker`
> ya lo reserva Django Channels (consumer de channel layers).

Args extra se reenvían a Celery:

```bash
python manage.py runworkers -- -l debug
python manage.py runbeat -- -l debug
```

### 🔹 Horarios

- El schedule está en código: `core/tasks/schedules.py` → `CELERY_BEAT_SCHEDULE`.
- Zona horaria: **UTC** (`CELERY_TIMEZONE`). Un `crontab(hour=3, minute=0)`
  es 03:00 UTC, no la hora local de Colombia.
- Beat usa **RedBeat** (candado en Redis) para no duplicar ejecuciones si
  hay más de una instancia.

### 🔹 Reintentos y rollback

**Reintentos (genéricos, selectivos)** — `BaseTask` (`core/tasks/base.py`):

- Auto-retry solo ante fallos transitorios: `ConnectionError`, `TimeoutError`,
  `OperationalError`, y `RetryableTaskError` (opt-in de dominio).
- Hasta 5 intentos con backoff + jitter (máx. 10 min).
- Los errores de negocio **no** se reintentan solos (evitar inundar la cola).

**Rollback (genérico, por compensación)** — `track_task_run` /
`TaskRunContext` (`core/tasks/run_context.py` + `compensation.py`):

- Tras un side effect confirmado, registrá el undo:

```python
with track_task_run(task_key='…', …) as run:
    with run.step('charge') as step:
        charge_id = charge()
        step.compensate('void_charge', lambda: void(charge_id))
    with run.step('activate'):
        activate()  # si falla → se ejecuta void_charge (LIFO)
```

- Si el run termina en `failed` (excepción o `mark_failed`), el contexto
  ejecuta las compensaciones en orden LIFO (best-effort; un undo fallido
  no detiene el resto ni traga la excepción original).
- El detalle queda en los logs del run (`--- compensations (rollback LIFO) ---`).
- `core` decide *cuándo* y *en qué orden*; el feature decide *qué* deshacer.
  Sweeps idempotentes (purgas GC) suelen no registrar compensaciones.

### 🔹 Cómo verificar

1. En Beat: logs del tipo `Scheduler: Sending due task …`.
2. En Worker: recibe y ejecuta esa task.
3. En admin → **Soporte → Tareas automatizadas**: aparece el run (y updates
   por WebSocket si el `runserver` está arriba).

### 🔹 Equivalente Celery CLI (opcional)

```bash
python -m celery -A base worker -l info --pool=solo --concurrency=1
python -m celery -A base beat -l info --scheduler redbeat.RedBeatScheduler
```

### 🔹 Ejecutar una tarea manualmente

```bash
python manage.py shell -c "from client.features.security.onboarding.tasks.purge import purge_expired_onboardings; purge_expired_onboardings.delay()"
```

Modo simulación (sin Celery):

```bash
python manage.py purge_expired_onboardings --dry-run
```

---

## 🛠️ Comandos propios de la plataforma

Los scripts operativos se ejecutan siempre con `manage.py`:

```bash
# Celery (tareas automatizadas) — terminales dedicadas
python manage.py runworkers
python manage.py runbeat

# Errores (homologa ERROR_REGISTRY → errors.json en client/admin)
python manage.py syncerrors
python manage.py syncerrors --dry-run

# Features por tenant
python manage.py sync_features
python manage.py sync_features --all

# Incidencias
python manage.py purge_incidents
python manage.py purge_incidents --days 90

# Onboarding
python manage.py purge_expired_onboardings --dry-run
python manage.py purge_unverified_tenants

# Logging / storage / admin
python manage.py run_log_retention
python manage.py ensure_profile_storage
python manage.py ensure_admin_profile_storage
python manage.py create_platform_admin
python manage.py runtests
```

Tras agregar un código en `core/errors/codes.py`, añade la traducción ES en
`core/errors/sync_i18n.py` y ejecuta `python manage.py syncerrors`.

---

## 📚 Documentación (Swagger)

Accede una vez el servidor esté corriendo:

- 🔗 http://localhost:8100/redoc/
- 🔗 http://localhost:8100/docs/

---

## 🧠 Buenas prácticas implementadas

- Jerarquía de features en 4 niveles (mundo → feature → lógica conjunta → entidad)
- Clean Architecture solo en L4 (`domain` / `application` / `infrastructure` / `presentation`)
- Uso de variables de entorno
- Procesos asíncronos desacoplados
- Testing por niveles (unit + integration)
- Soporte multi-instancia con locks distribuidos (RedBeat)

---

## 📌 Notas finales

Este proyecto está diseñado para escalar y adaptarse a arquitecturas modernas basadas en microservicios y procesamiento distribuido.

---

💬 *Si vas a contribuir, asegúrate de seguir las convenciones del proyecto y mantener consistencia en la arquitectura.*
