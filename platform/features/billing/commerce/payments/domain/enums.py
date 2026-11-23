"""
Enums del dominio de pagos.

Estos valores son la fuente de verdad del *contrato* interno. Los
proveedores externos pueden usar nombres distintos para los mismos
conceptos; sus adapters deben traducir hacia estos enums.
"""

from enum import Enum


class ChargeStatus(str, Enum):
    """Estados posibles del ciclo de vida de un :class:`Charge`."""

    PENDING            = 'pending'
    PROCESSING         = 'processing'
    REQUIRES_ACTION    = 'requires_action'
    AUTHORIZED         = 'authorized'
    CAPTURED           = 'captured'
    FAILED             = 'failed'
    CANCELED           = 'canceled'
    REFUNDED           = 'refunded'
    PARTIALLY_REFUNDED = 'partially_refunded'
    DISPUTED           = 'disputed'

    @classmethod
    def terminal(cls) -> set['ChargeStatus']:
        return {cls.FAILED, cls.CANCELED, cls.REFUNDED}

    @classmethod
    def successful(cls) -> set['ChargeStatus']:
        return {cls.CAPTURED, cls.AUTHORIZED, cls.PARTIALLY_REFUNDED}


class MethodType(str, Enum):
    """Tipos de método de pago soportados por la abstracción."""

    CARD          = 'card'
    BANK_TRANSFER = 'bank_transfer'
    PSE           = 'pse'
    WALLET        = 'wallet'
    VOUCHER       = 'voucher'
    BNPL          = 'bnpl'
    CRYPTO        = 'crypto'
    OTHER         = 'other'


class NextActionType(str, Enum):
    REDIRECT        = 'redirect'
    DISPLAY_QR      = 'display_qr'
    DISPLAY_VOUCHER = 'display_voucher'
    AWAIT_WEBHOOK   = 'await_webhook'


class GatewayProvider(str, Enum):
    """
    Identificadores de adapter.

    El valor literal aquí es la clave usada en el registry y en el
    parámetro de plataforma ``PAYMENT_PROVIDER``. Agregar uno nuevo
    requiere: (1) extender este enum, (2) crear el adapter,
    (3) registrarlo en :mod:`...gateways.registry`.
    """

    SIMULATOR     = 'simulator'
    STRIPE        = 'stripe'
    WOMPI         = 'wompi'
    PAYU          = 'payu'
    MERCADOPAGO   = 'mercadopago'
    EPAYCO        = 'epayco'
    PAYPAL        = 'paypal'


class WebhookEventType(str, Enum):
    """
    Eventos normalizados de webhook (lenguaje interno).

    Cada provider tiene su propio nombre (``payment_intent.succeeded`` en
    Stripe, ``transaction.updated`` en Wompi, etc.); el WebhookTranslator
    del provider los mapea a estos.
    """

    CHARGE_CREATED            = 'charge.created'
    CHARGE_AUTHORIZED         = 'charge.authorized'
    CHARGE_CAPTURED           = 'charge.captured'
    CHARGE_FAILED             = 'charge.failed'
    CHARGE_CANCELED           = 'charge.canceled'
    CHARGE_REFUNDED           = 'charge.refunded'
    CHARGE_PARTIALLY_REFUNDED = 'charge.partially_refunded'
    CHARGE_DISPUTED           = 'charge.disputed'
    CHARGE_REQUIRES_ACTION    = 'charge.requires_action'


class AttemptOperation(str, Enum):
    CREATE  = 'create'
    CONFIRM = 'confirm'
    CAPTURE = 'capture'
    CANCEL  = 'cancel'
    REFUND  = 'refund'
    FETCH   = 'fetch'


class AttemptResult(str, Enum):
    SUCCEEDED = 'succeeded'
    FAILED    = 'failed'
    PENDING   = 'pending'
