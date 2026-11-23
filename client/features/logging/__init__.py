"""
client.features.logging
───────────────────────
Sistema centralizado de logging para el WMS.

Punto de entrada rápido:
    from client.features.logging.facade.factory import LogManagerFactory
    from client.features.logging.facade.context import LogContextBuilder

    log = LogManagerFactory.create()
    context = LogContextBuilder.from_request(request)
    log.audit(context, AuditLogInputSchema(...))
"""
