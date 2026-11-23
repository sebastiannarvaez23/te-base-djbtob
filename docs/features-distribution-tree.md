# Árbol de distribución de features — base

> **Jerarquía canónica (L1–L4) y auditoría:** ver
> [`features-hierarchy-audit.md`](./features-hierarchy-audit.md).
> Este archivo es un inventario de capas presentes; no valida el estándar de 4 niveles.

Mapa de features por mundo (`client` / `platform` / `handbook`) con distribución Clean Architecture.

Convención por hoja:

```
nombre: descripción | capas CA presentes
```

Capas típicas: `domain` → `application` → `infrastructure` → `presentation` (+ `migrations` / `models.py` / `apps.py` cuando aplica).

Si un directorio **no** es feature hoja (no tiene `domain/`), se desciende un nivel hasta encontrar la distribución CA.

---

## base

- **client**: Tenant (schema por empresa) — WMS operativo
  - **features**
    - **communication**: Comunicación in-app del tenant
      - **assistant**: Familia assistant (L3, sin CA)
        - **chat**: Asistente conversacional assistant (chat SLM) por tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · realtime`
      - **messaging**: Mensajería in-app (L3)
        - **inbox**: Bandeja de mensajes / notificaciones in-app del tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks`
    - **integrations**: Conexiones e integraciones ERP/terceros del tenant (L2 sin CA)
      - **connections**: Familia de conexiones (L3)
        - **profile**: Perfiles / sync jobs de integración | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks`
      - **oauth**: Familia OAuth (L3)
        - **client**: OAuth de conectores / scopes para apps externas | `domain · application · infrastructure · presentation · models.py`
      - **facade**: Facade pública de integraciones (sin capas CA propias) | `—`
    - **partners**: Partners / maestros de terceros (L2 sin CA)
      - **third_parties**: Familia third parties (L3)
        - **party**: Terceros (clientes, proveedores, carriers) del WMS | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **logging**: Logging transversal del tenant (L2)
      - **audit_trail**: Auditoría (L3)
        - **audit**: Logs de auditoría CRUD de entidades | `domain · application · infrastructure · migrations · models.py · apps.py`
      - **facade**: Facade/factory de logging transversal (helper) | `—`
      - **ops**: Eventos operativos (L3)
        - **integration**: Logs de operaciones de integración / conectores | `domain · application · infrastructure · migrations · models.py · apps.py`
        - **inventory**: Eventos de inventario (movimientos, ajustes) | `domain · application · infrastructure · migrations · models.py · apps.py`
        - **operations**: Eventos operativos de warehouse | `domain · application · infrastructure · migrations · models.py · apps.py`
      - **security**: Logs de seguridad (L3)
        - **security**: Logs de seguridad (auth, permisos) | `domain · application · infrastructure · migrations · models.py · apps.py`
      - **system**: Sistema (L3)
        - **config**: Configuración de retención y categorías de logging | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **errors**: Registro de errores capturados en el tenant | `domain · application · infrastructure`
        - **performance**: Métricas / logs de rendimiento | `domain · application · infrastructure`
        - **retention**: Políticas y ejecución de retención de logs | `domain · application · infrastructure · management`
        - **system**: Logs de sistema del tenant | `domain · application · infrastructure`
    - **security**: Seguridad e identidad del tenant (L2)
      - **access**: Acceso (L3)
        - **features**: Features habilitadas del tenant (catálogo efectivo) | `domain · application · infrastructure · presentation`
        - **roles**: Roles y permisos del tenant | `domain · application · infrastructure · presentation`
      - **identity**: Identidad (L3)
        - **identity**: Identidad / perfil del usuario tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **users**: CRUD de usuarios del tenant | `domain · application · infrastructure · presentation`
      - **lifecycle**: Ciclo de vida auth (L3)
        - **auth**: Autenticación JWT y sesión del usuario tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **onboarding**: Onboarding de empresa / primer acceso tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks · management`
        - **registration**: Registro de usuarios en el tenant | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
    - **warehouse**: Dominio WMS operativo (L2 sin CA)
      - **foundation**: Kernel compartido / helper L2 (idempotencia, outbox, UoW; sin capas CA) | `contracts.py · reliability.py · models.py · apps.py · migrations`
      - **fulfillment**: Flujo outbound (L3)
        - **dispatches**: Despacho / shipping de pedidos | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **orders**: Pedidos de salida (outbound orders) | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **packing**: Packing / empaque de pedidos | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **picking**: Picking / preparación de pedidos | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **inbound**: Flujo de entrada (L3)
        - **receiving**: Recepción de mercancía | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **returns**: Devoluciones / returns | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **inventory**: Inventario: catálogo, saldos y stock (L3)
        - **balances**: Saldos / balances de inventario por ubicación | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **reference**: Catálogo de referencias / SKUs e importación | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **stock**: Movimientos y stock operativo | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **ops**: Operaciones avanzadas (L3)
        - **operations**: Operaciones transversales de warehouse | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **site**: Instalaciones (L3)
        - **facilities**: Bodegas, zonas, ubicaciones, capacidad | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`

- **platform**: Admin SaaS (schema público)
  - **features**
    - **billing**: Billing / suscripciones SaaS (L2)
      - **common**: Helpers compartidos de billing | `—`
      - **commerce**: Cobros y promociones (L3)
        - **invoice**: Facturas de suscripción SaaS | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **payment_method**: Métodos de pago de la empresa | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **payments**: Pagos y estado de cobro | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **promotion**: Promociones y reglas de descuento | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks · management`
        - **refund**: Reembolsos | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks`
      - **quota**: Cupos (L3)
        - **quota_enforcement**: Enforcement de cupos por entidades activas | `domain · application · infrastructure · apps.py`
      - **subscription**: Familia de suscripción (L3)
        - **subscription**: Suscripciones de empresas | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks`
        - **subscription_functionality**: Funcionalidades incluidas en la suscripción | `domain · application · infrastructure · presentation · migrations · apps.py`
        - **subscription_limit**: Límites / cupos de la suscripción | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **subscription_module**: Módulos incluidos en la suscripción | `domain · application · infrastructure · presentation · migrations · apps.py`
    - **communication**: Comunicación de plataforma (L2)
      - **email**: Correo (L3)
        - **email_sender**: Envío de correos de plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **email_template**: Plantillas de email de plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
      - **messaging**: Mensajería (L3)
        - **inbox**: Inbox / mensajería admin de plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **notification**: Despacho de notificaciones (helper) | `—`
    - **company**: Gestión de empresas (L2)
      - **tenant**: Tenant (L3)
        - **company**: Empresas (tenants) de la plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks · management`
        - **users**: Usuarios de empresas (visión plataforma) | `domain · application · infrastructure · presentation`
    - **compliance**: Cumplimiento normativo (L2)
      - **policy**: Familia policy (L3)
        - **policy**: Políticas de cumplimiento (términos, privacidad) | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **configuration**: Configuración global (L2)
      - **assistant**: Familia assistant config (L3)
        - **assistant**: Configuración global del asistente IA | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **landing**: Contenido landing (L3)
        - **landing**: Contenido / catálogo de landing | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **testimonial**: Testimonios para marketing / landing | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
      - **parameters**: Parámetros (L3)
        - **parameter**: Parámetros de configuración de plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **parameter_type**: Tipos de parámetro | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **documents**: Documentos y plantillas (L2)
      - **document_template**: Familia document_template (L3)
        - **document_template**: Plantillas de documentos / PDF | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **geography**: Geografía (L2)
      - **location**: Familia location (L3)
        - **location**: Catálogo geográfico (países, ciudades, etc.) | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **integrations**: Integraciones plataforma (L2)
      - **connector_catalog**: Familia connector_catalog (L3)
        - **connector_catalog**: Catálogo global de conectores | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
    - **release**: Release / feature flags (L2)
      - **feature_flag**: Familia feature_flag (L3)
        - **feature_flag**: Feature flags de release | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
    - **security**: Seguridad de administradores (L2)
      - **access**: Catálogo de acceso (L3)
        - **functionalities**: Funcionalidades (permisos atómicos) | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **modules**: Módulos admin | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **roles**: Roles de administradores | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **sections**: Secciones del menú / ACL admin | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **auth**: Auth admin (L3)
        - **auth**: Auth de administradores de plataforma | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **identity**: Identidad admin (L3)
        - **identity**: Perfil de administradores | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
        - **sessions**: Sesiones de admin | `domain · application · infrastructure · presentation`
        - **users**: CRUD de usuarios administradores | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
    - **support**: Soporte y operaciones (L2)
      - **incidents**: Incidencias (L3)
        - **incident**: Incidencias reportadas desde errores 500 | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · management`
      - **ops**: Ops (L3)
        - **task_monitor**: Monitoreo de tareas Celery / jobs | `domain · application · infrastructure · presentation · migrations · models.py · apps.py · tasks`

- **handbook**: Documentación de plataforma (schema público)
  - **features**
    - **docs**: L2 único (candidato `wa-handbook-msv`; sin CA)
      - **content**: Contenido del handbook (L3)
        - **catalog**: Catálogo de documentación (audiencias, features) | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **page**: Páginas del handbook | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
      - **governance**: Gobierno de cambios / ingest (L3)
        - **change_request**: Solicitudes de cambio de documentación | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`
        - **ingest**: Ingesta / sincronización de contenido del handbook | `domain · application · infrastructure · presentation · migrations · models.py · apps.py`

- **core**: utilidades transversales (no es mundo de features; varios módulos siguen puertos/adaptadores)
  - **ai**: Módulo transversal de IA (puertos chat/embed + providers) | `domain · infrastructure`
  - **email**: Transporte de correo de plataforma (SMTP/Resend) | `domain · application · infrastructure`
  - **flags**: Evaluación de feature flags transversales | `domain · application · infrastructure`
  - **integrations**: Runtime de integraciones (conectores, idempotencia, runner) | `domain · application · infrastructure`
  - **signing**: Firma / verificación criptográfica de payloads | `domain`
  - **storage**: Almacenamiento de archivos (puertos + adapters) | `domain · application · infrastructure`
