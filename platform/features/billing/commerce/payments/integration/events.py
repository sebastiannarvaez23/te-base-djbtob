"""
Evento de integración ``InvoiceIssued``.

Emitido por :class:`InvoiceBillingListener` una vez que una factura queda
*emitida y pagada* como resultado de un pago capturado (sea preexistente o
auto-generada). Lo consume :class:`InvoiceDeliveryListener` para enviarla.

Por qué existe (en vez de que delivery escuche ``PaymentCaptured``):

  * **Sin mutación del evento de pago.** Antes, billing escribía el id de la
    factura recién creada *dentro* del ``PaymentCaptured`` para que delivery
    —siguiente handler— lo leyera. Eso acoplaba ambos al orden de suscripción
    y al bus síncrono. Ahora billing publica este evento con el id ya resuelto.

  * **El enrutado del correo viaja en un evento de billing, no en el de pago.**
    El ``email_template_code`` / ``email_context`` (p.ej. SUB_UPGRADE) los
    interpreta sólo la capa de integración de billing; el dominio de pagos
    permanece agnóstico.

Se publica por el mismo bus in-process de pagos (que despacha por ``type``).
"""
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class InvoiceIssued(BaseModel):
    invoice_id: uuid.UUID
    company_id: uuid.UUID
    charge_id: Optional[uuid.UUID] = None
    # Pista de entrega — la interpreta InvoiceDeliveryListener.
    email_template_code: Optional[str] = None
    email_context: Optional[dict[str, Any]] = None
    recipient_email: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
