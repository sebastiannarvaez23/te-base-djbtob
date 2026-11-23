# FASE 0 — Cimientos (DB wadw + settings + router)

> **Navegación:** [Resumen teórico](00-resumen-teorico.md) · **Fase 0** · Siguiente → [Fase 1](fase-1-capa-transversal.md)

> **Continuidad.** Prerrequisito: leer la [auditoría](00-resumen-teorico.md#1-auditoría-del-estado-actual).
> Hoy solo existe `DATABASES['default']` → `wadb`. Esta fase crea la tubería
> física hacia `wadw` **sin** pipelines de negocio.

**Objetivo:** que el entorno local (y el contrato de settings de prod) tengan
una base analítica alcanzable, con alias Django `analytics`, healthcheck y
router que impida contaminar OLTP ↔ DW.

**Qué queda fuera:** modelos dimensionales, ETL, Celery analytics, APIs.

---

## Explicación arquitectónica

Separar **compute/storage analítico** del OLTP desde el día 1 evita que
reportes bloqueen recepciones/picking y permite retention/backup distintos.
El alias se llama `analytics` (estable en código); el nombre físico de la DB
es `wadw` (ops/infra).

## Justificación

- Reutiliza Postgres ya conocido (bajo costo, sin tecnología nueva).
- Deja el camino abierto a mover `wadw` a otro host sin tocar pipelines.
- El router explícito es obligatorio: sin él, un `.save()` accidental podría
  escribir facts en el schema tenant o modelos OLTP en wadw.

## Impacto

| Área | Cambio |
|------|--------|
| `docker-compose.yml` / init DB | Crear database `wadw` (mismo servicio o servicio dedicado) |
| `base/settings/*.py` + `.env.ex` | `DATABASES['analytics']`, vars `DW_*` o reuso host con `DW_NAME` |
| `DATABASE_ROUTERS` | Añadir router analytics **antes** de TenantSyncRouter |
| README | Cómo levantar wadw y verificar conexión |
| Tests | Override `DATABASES['analytics']` (misma DB test o sqlite no aplica — usar Postgres test DB) |

> **Nota router:** `TenantSyncRouter.allow_migrate` retorna `False` para
> cualquier alias ≠ `default`. Si el router analytics va *después*, las
> migraciones de wadw nunca correrían. Por eso `AnalyticsRouter` va primero.

## Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Dev olvida crear `wadw` | Init script + healthcheck en compose; fail-fast en `db_health` |
| Migraciones corren al alias equivocado | Documentar `migrate --database=analytics`; app DW aún no existe (Fase 2) |
| Credenciales compartidas OLTP/DW | Mismo user en dev; en prod user read/write separado a medio plazo |

## Actividades

- [x] Definir variables: `DW_NAME=wadw`, host/port/user/password (defaults al mismo Postgres de OLTP en local).
- [x] Añadir creación de DB `wadw` al bootstrap Docker (script init o documentación `CREATE DATABASE`).
- [x] Registrar `DATABASES['analytics']` con `ENGINE` Postgres estándar (**no** `django_tenants.postgresql_backend`).
- [x] Implementar `AnalyticsRouter`: apps/modelos analytics → `analytics`; resto → `default`; allow migrate solo en DB correcta.
- [x] Extender `core/db_health.py` (o equivalente) para ping de `analytics`.
- [x] Actualizar `.env.ex` y README (sin secretos reales).
- [x] Test: settings cargan dos DBs; router unit test con modelos fake o app stub.

## Buenas prácticas

- No uses `django_tenants` backend en wadw.
- No registres aún apps de facts en `TENANT_APPS`.
- Mantén `CONN_MAX_AGE` conservador en analytics.

## Cómo probarlo

```bash
# Tras compose up
psql -h 127.0.0.1 -p 3000 -U wa_user -c "\\l" | grep wadw
python manage.py shell -c "from django.db import connections; connections['analytics'].ensure_connection(); print('ok')"
```

## Definición de Done

- [x] `wadw` existe en el entorno local documentado.
- [x] `connections['analytics']` conecta.
- [x] Router + healthcheck verificados por test o checklist manual en README.
- [x] Ningún pipeline ni modelo dimensional mergeado aún.
