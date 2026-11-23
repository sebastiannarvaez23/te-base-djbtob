# Features Catalog — Pendientes de construcción

Este archivo documenta todas las funcionalidades (features) identificadas para el sistema de permisos de roles.
Son la fuente para construir el catálogo definitivo en la base de datos mediante el comando `sync_features`.

> El catálogo activo vive en `client/features/security/registration/feature_registry.py`.
> Ejecutar `python manage.py sync_features` para sincronizar con la base de datos.

---

## dashboard
**features:**
`view-summary`, `configurable-widgets`, `real-time-metrics`, `alerts-notifications`,
`quick-access`, `kpis`, `pending-orders-view`, `critical-inventory-view`, `warehouse-period-filters`

**ai:**
`daily-demand-prediction`, `predictive-alerts`, `smart-day-summary`

---

## orders
**features:**
`create`, `edit`, `cancel`, `view-status`, `inventory-validation`, `inventory-reservation`,
`priorities`, `multi-warehouse`, `attachments`, `traceability`, `split`, `consolidation`,
`backorders`, `cross-docking`, `warehouse-assignment-rules`, `picking-rules`, `wave-picking`,
`multi-currency`, `multi-company`, `credit-control`, `risk-blocks`, `sla`, `dropshipping`, `antifraud`

**ai:**
`priority-prediction`, `delay-prediction`, `optimal-warehouse`, `picking-grouping`,
`stockout-prediction`, `order-anomaly-detection`, `risk-classification`, `carrier-suggestion`,
`dispatch-time-prediction`, `packaging-recommendation`

---

## reception
**features:**
`create`, `edit`, `cancel`, `reception-by-po`, `reception-without-po`, `quality-control`,
`blind-count`, `differences-log`, `location-assignment`, `customer-returns`, `warehouse-transfers`,
`product-labeling`, `photos-attachments`, `lot-series-traceability`, `multi-warehouse`

**ai:**
`auto-location-suggestion`, `anomaly-detection`, `volume-prediction`

---

## location
**features:**
`create`, `edit`, `deactivate`, `zone-management`, `location-types`, `max-capacity`,
`product-restrictions`, `warehouse-map`, `inventory-relocation`, `temperature-control`,
`location-blocking`, `multi-warehouse`

**ai:**
`optimal-slotting`, `occupancy-prediction`, `layout-optimization`

---

## inventories
**features:**
`references-view`, `references-create`, `references-edit`, `references-deactivate`,
`references-import`, `reference-types-manage`,
`real-time-view`, `adjustments`, `physical-counts`, `general-inventory`, `lot-expiry-control`,
`serial-number-control`, `inventory-blocking`, `warehouse-transfers`, `location-transfers`,
`movement-history`, `valuation`, `multi-currency`, `multi-warehouse`, `min-max-alerts`,
`full-traceability`, `quarantine`, `packaging-management`, `kardex`

**ai:**
`stockout-prediction`, `reorder-recommendation`, `abc-classification`, `obsolete-detection`,
`demand-prediction`, `level-optimization`

---

## picking
**features:**
`create-tasks`, `assign-tasks`, `individual-picking`, `batch-picking`, `zone-picking`,
`wave-picking`, `picking-rules`, `voice-guided`, `rf-scanner-guided`, `pick-consolidation`,
`partial-picking`, `traceability`, `quality-control`, `task-reassignment`,
`productivity-history`, `multi-warehouse`

**ai:**
`route-optimization`, `order-grouping`, `time-prediction`, `auto-assignment`, `error-detection`

---

## packing
**features:**
`create-tasks`, `assign-packers`, `product-verification`, `package-type-selection`,
`dimensions-weight`, `label-generation`, `quality-control`, `multi-box`, `attachments`,
`special-instructions`, `material-tracking`, `operator-history`

**ai:**
`optimal-package-recommendation`, `dimensions-cost-optimization`, `time-prediction`, `anomaly-detection`

---

## dispatches
**features:**
`create`, `edit`, `cancel`, `carrier-assignment`, `dispatch-guide`, `route-grouping`,
`vehicle-load-control`, `digital-delivery-receipt`, `dispatch-photos`, `exit-confirmation`,
`traceability`, `customer-returns`, `temperature-control`, `multi-warehouse`, `history`

**ai:**
`route-optimization`, `delivery-time-prediction`, `zone-grouping`, `carrier-suggestion`, `demand-prediction`

---

## returns
**features:**
`create`, `edit`, `cancel`, `view`, `authorize`, `receive`, `inspect`,
`disposition`, `putaway`, `close`, `history`, `reasons`, `photos-attachments`,
`lot-series-traceability`, `without-order`, `partial`, `vendor-returns`,
`exchanges`, `multi-warehouse`, `traceability`

**ai:**
`disposition-suggestion`, `anomaly-detection`, `volume-prediction`, `fraud-detection`

Plan HU: [`docs/hu-operative/returns/`](hu-operative/returns/00-vision-fronteras.md).
`reception.customer-returns` = bridge inbound físico; `dispatches.customer-returns` =
rechazo en muelle **antes** de `SHIP`. Ninguna de las dos posee el RMA.

---

## shipping
**features:**
`carrier-management`, `rates-agreements`, `label-generation`, `tracking`,
`customer-notifications`, `failed-shipments`, `reshipments`, `international`,
`export-documents`, `insurance`, `express-standard`, `multi-carrier`,
`logistics-integration`, `history`

**ai:**
`optimal-carrier-selection`, `delivery-time-prediction`, `failed-shipment-prediction`, `cost-optimization`

---

## third_parties
**features:**
`client-management`, `supplier-management`, `carrier-management`,
`external-warehouse-management`, `contact-info`, `transaction-history`,
`credit-control`, `risk-blocking`, `documents`, `classification`,
`multi-company`, `sla`, `commercial-terms`

**ai:**
`credit-risk-classification`, `payment-behavior-prediction`, `transaction-anomaly-detection`

---

## users_roles
**features:**
`create-users`, `edit-users`, `deactivate-users`, `create-roles`, `edit-roles`,
`assign-roles`, `module-permissions`, `feature-permissions`, `access-history`,
`two-factor-auth`, `password-recovery`, `password-policy`, `active-sessions`, `change-audit`

---

## tasks
**features:**
`create`, `edit`, `assign`, `prioritization`, `status-tracking`, `deadlines`,
`alerts-reminders`, `recurring-tasks`, `comments`, `attachments`, `history`,
`templates`, `notifications`

**ai:**
`auto-prioritization`, `completion-time-prediction`, `smart-assignment`, `bottleneck-detection`

---

## integrations
**features:**
`erp-integration`, `ecommerce-integration`, `marketplace-integration`,
`carrier-integration`, `webhooks`, `rest-api`, `import-export`,
`inventory-sync`, `order-sync`, `product-sync`, `integration-logs`,
`data-mapping`, `oauth`

---

## automation
**features:**
`create-rules`, `edit-rules`, `deactivate-rules`, `event-triggers`, `cron-triggers`,
`advanced-conditions`, `chained-actions`, `auto-notifications`, `auto-task-assignment`,
`escalation-rules`, `execution-history`, `rule-debugging`

**ai:**
`rule-suggestion`, `pattern-detection`, `workflow-optimization`

---

## analytics
**features:**
`custom-dashboards`, `predefined-reports`, `adhoc-reports`, `export-reports`,
`picking-metrics`, `inventory-metrics`, `dispatch-metrics`, `reception-metrics`,
`returns-metrics`, `operational-kpis`, `operator-productivity`, `inventory-rotation`,
`period-comparison`

**ai:**
`demand-predictive-analysis`, `trend-detection`, `operational-anomalies`,
`improvement-recommendations`, `sales-forecast`

---

## audit
**features:**
`event-logging`, `advanced-filters`, `log-export`, `critical-alerts`,
`entity-change-history`, `user-traceability`, `access-audit`,
`config-change-audit`, `configurable-retention`, `audit-reports`

---

## settings
**features:**
`company-config`, `warehouse-management`, `printers-devices`, `notifications-config`,
`document-templates`, `currency-config`, `language-config`, `timezone-config`,
`product-categories`, `units-of-measure`, `security-params`, `backup-config`,
`ui-customization`, `subscription-billing`
