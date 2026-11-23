"""Códigos de error — billing."""
from enum import Enum


class SubscriptionErrorCode(str, Enum):
    """Suscripción."""

    SUB_NO_ACTIVE              = 'SUB_001'  # Empresa sin suscripción activa
    SUB_FEATURE_DENIED         = 'SUB_002'  # Funcionalidad no incluida en el plan
    SUB_QUOTA_EXCEEDED         = 'SUB_003'  # Tope de uso excedido
    SUB_CHANGE_ALREADY_PENDING = 'SUB_004'  # Ya hay un cambio de plan en proceso
    SUB_PERIOD_BIND_FAILED     = 'SUB_005'  # No se pudo enlazar cobro/factura al período
    SUB_RECOVERY_DENIED        = 'SUB_006'  # Módulo no permitido en modo regularización de pago
    SUB_NO_SUSPENDED           = 'SUB_007'  # No hay período suspendido que restaurar
    SUB_CATALOG_SERVICE        = 'SUB_008'  # Servicio de catálogo no asociable
    SUB_CATALOG_UNAVAILABLE    = 'SUB_009'  # No se pudo leer el catálogo de Neurana


SUB_REGISTRY: dict[SubscriptionErrorCode, dict] = {
    SubscriptionErrorCode.SUB_NO_ACTIVE: {
        'http_status': 403,
        'message': 'No active subscription',
        'detail': 'This company does not have an active subscription plan.',
    },
    SubscriptionErrorCode.SUB_FEATURE_DENIED: {
        'http_status': 403,
        'message': 'Feature not included in plan',
        'detail': 'Your current subscription plan does not include this feature.',
    },
    SubscriptionErrorCode.SUB_QUOTA_EXCEEDED: {
        'http_status': 429,
        'message': 'Usage limit exceeded',
        'detail': 'You have reached the usage limit for this feature in your current plan.',
    },
    SubscriptionErrorCode.SUB_CHANGE_ALREADY_PENDING: {
        'http_status': 409,
        'message': 'Plan change already in progress',
        'detail': 'You already have a plan change in progress. You can request another once it becomes active.',
    },
    SubscriptionErrorCode.SUB_PERIOD_BIND_FAILED: {
        'http_status': 500,
        'message': 'Could not bind payment to subscription period',
        'detail': 'The payment could not be linked to the subscription period. Retry or contact support.',
    },
    SubscriptionErrorCode.SUB_RECOVERY_DENIED: {
        'http_status': 403,
        'message': 'Billing recovery access only',
        'detail': 'While your subscription is suspended, you can only access billing and payment settings.',
    },
    SubscriptionErrorCode.SUB_NO_SUSPENDED: {
        'http_status': 404,
        'message': 'No suspended subscription to restore',
        'detail': 'There is no suspended subscription period that can be restored.',
    },
    SubscriptionErrorCode.SUB_CATALOG_SERVICE: {
        'http_status': 400,
        'message': 'Catalog service cannot be linked',
        'detail': 'That catalog service cannot be linked to the plan. Choose an active service from the product catalog.',
    },
    SubscriptionErrorCode.SUB_CATALOG_UNAVAILABLE: {
        'http_status': 503,
        'message': 'Product catalog unavailable',
        'detail': 'The product catalog could not be read. Try again in a moment.',
    },
}


class RefundErrorCode(str, Enum):
    """Reembolsos."""

    RFD_WINDOW_CLOSED    = 'RFD_001'  # Pasaron más de 24 h desde el inicio del período
    RFD_COOLDOWN         = 'RFD_002'  # Reembolso bloqueado por 3 meses tras un relevo
    RFD_NOT_RELEVO       = 'RFD_003'  # El plan destino no es un relevo (gratis o más barato)
    RFD_NOT_ELIGIBLE     = 'RFD_004'  # No hay cobro capturado reembolsable en esta vigencia
    RFD_OPEN_TICKET      = 'RFD_005'  # Ya hay una solicitud de reembolso en curso
    RFD_TARGET_NOT_FOUND = 'RFD_006'  # Plan destino inexistente o inactivo
    RFD_TICKET_NOT_FOUND = 'RFD_007'  # Solicitud de reembolso no encontrada
    RFD_NOT_PENDING      = 'RFD_008'  # La solicitud ya no está pendiente de aprobación


RFD_REGISTRY: dict[RefundErrorCode, dict] = {
    RefundErrorCode.RFD_WINDOW_CLOSED: {
        'http_status': 403,
        'message': 'Refund window closed',
        'detail': 'Refunds are only available within 24 hours of activating the current plan.',
    },
    RefundErrorCode.RFD_COOLDOWN: {
        'http_status': 403,
        'message': 'Refund cooldown active',
        'detail': 'After switching plans with a refund you must wait 3 months before requesting another.',
    },
    RefundErrorCode.RFD_NOT_RELEVO: {
        'http_status': 400,
        'message': 'Target plan is not a downgrade',
        'detail': 'A refund only applies when you switch to the free plan or to a cheaper plan.',
    },
    RefundErrorCode.RFD_NOT_ELIGIBLE: {
        'http_status': 409,
        'message': 'No refundable payment',
        'detail': 'There is no captured payment on this billing period that can be returned.',
    },
    RefundErrorCode.RFD_OPEN_TICKET: {
        'http_status': 409,
        'message': 'Refund already in progress',
        'detail': 'You already have a refund request in progress. Follow that ticket until it completes.',
    },
    RefundErrorCode.RFD_TARGET_NOT_FOUND: {
        'http_status': 404,
        'message': 'Target plan not found',
        'detail': 'The plan you want to switch to is not available.',
    },
    RefundErrorCode.RFD_TICKET_NOT_FOUND: {
        'http_status': 404,
        'message': 'Refund request not found',
        'detail': 'That refund request does not exist for your company.',
    },
    RefundErrorCode.RFD_NOT_PENDING: {
        'http_status': 409,
        'message': 'Refund is not pending approval',
        'detail': 'Only a pending refund request can be approved or rejected.',
    },
}


class SubscriptionLimitErrorCode(str, Enum):
    """Topes de suscripción."""

    SLIMIT_NOT_FOUND = 'SLIMIT_001'  # Tope de suscripción no encontrado
    SLIMIT_DUPLICATE = 'SLIMIT_002'  # Ya existe un tope para esa funcionalidad en la suscripción


SLIMIT_REGISTRY: dict[SubscriptionLimitErrorCode, dict] = {
    SubscriptionLimitErrorCode.SLIMIT_NOT_FOUND: {
        'http_status': 404,
        'message': 'Subscription limit not found',
        'detail': 'The requested subscription limit does not exist.',
    },
    SubscriptionLimitErrorCode.SLIMIT_DUPLICATE: {
        'http_status': 409,
        'message': 'Duplicate subscription limit',
        'detail': 'A limit for this functionality already exists in the given subscription.',
    },
}


class InvoiceErrorCode(str, Enum):
    """Facturas."""

    INV_NOT_FOUND         = 'INV_001'  # Factura no encontrada
    INV_NO_RECIPIENT      = 'INV_002'  # No se pudo determinar destinatario del correo
    INV_EMAIL_SEND_FAILED = 'INV_003'  # Falló el envío del correo con la factura adjunta


INV_REGISTRY: dict[InvoiceErrorCode, dict] = {
    InvoiceErrorCode.INV_NOT_FOUND: {
        'http_status': 404,
        'message': 'Invoice not found',
        'detail': 'The requested invoice does not exist.',
    },
    InvoiceErrorCode.INV_NO_RECIPIENT: {
        'http_status': 400,
        'message': 'No invoice recipient',
        'detail': 'Could not determine an email recipient for this invoice.',
    },
    InvoiceErrorCode.INV_EMAIL_SEND_FAILED: {
        'http_status': 502,
        'message': 'Invoice email failed',
        'detail': 'The invoice PDF was generated but the email could not be delivered.',
    },
}


class PromoErrorCode(str, Enum):
    """Promociones."""

    PROMO_NOT_FOUND        = 'PROMO_001'  # Serial de bono no encontrado
    PROMO_NOT_ACTIVE       = 'PROMO_002'  # Bono no activo
    PROMO_PLAN_INELIGIBLE  = 'PROMO_003'  # Plan no elegible o inferior al actual
    PROMO_OUT_OF_WINDOW    = 'PROMO_004'  # Fuera de vigencia de redención
    PROMO_SCOPE_DENIED     = 'PROMO_005'  # Alcance no permite esta empresa
    PROMO_ALREADY_CONSUMED = 'PROMO_006'  # Bono ya consumido
    PROMO_INCOMPATIBLE     = 'PROMO_007'  # Tipo incompatible con la operación
    PROMO_IDEMPOTENCY_HIT  = 'PROMO_008'  # Redención ya procesada
    PROMO_INVALID_INPUT    = 'PROMO_009'  # Validación de entrada
    PROMO_INTERNAL         = 'PROMO_010'  # Error interno
    PROMO_BENEFIT_ACTIVE   = 'PROMO_011'  # Empresa ya tiene beneficio activo


PROMO_REGISTRY: dict[PromoErrorCode, dict] = {
    PromoErrorCode.PROMO_NOT_FOUND: {
        'http_status': 404,
        'message': 'Voucher not found',
        'detail': 'The promotion voucher serial was not found.',
    },
    PromoErrorCode.PROMO_NOT_ACTIVE: {
        'http_status': 400,
        'message': 'Voucher not active',
        'detail': 'This promotion voucher is not active.',
    },
    PromoErrorCode.PROMO_PLAN_INELIGIBLE: {
        'http_status': 400,
        'message': 'Plan not eligible',
        'detail': 'The selected subscription plan is not eligible for this voucher.',
    },
    PromoErrorCode.PROMO_OUT_OF_WINDOW: {
        'http_status': 400,
        'message': 'Voucher expired',
        'detail': 'This voucher is outside its redemption window.',
    },
    PromoErrorCode.PROMO_SCOPE_DENIED: {
        'http_status': 403,
        'message': 'Voucher scope denied',
        'detail': 'This voucher cannot be redeemed by this company.',
    },
    PromoErrorCode.PROMO_ALREADY_CONSUMED: {
        'http_status': 409,
        'message': 'Voucher already consumed',
        'detail': 'This promotion voucher has already been redeemed.',
    },
    PromoErrorCode.PROMO_INCOMPATIBLE: {
        'http_status': 400,
        'message': 'Voucher incompatible',
        'detail': 'This voucher cannot be used for the requested operation.',
    },
    PromoErrorCode.PROMO_IDEMPOTENCY_HIT: {
        'http_status': 409,
        'message': 'Redemption already processed',
        'detail': 'This voucher redemption was already processed.',
    },
    PromoErrorCode.PROMO_INVALID_INPUT: {
        'http_status': 400,
        'message': 'Invalid voucher input',
        'detail': 'The promotion voucher input failed validation.',
    },
    PromoErrorCode.PROMO_INTERNAL: {
        'http_status': 500,
        'message': 'Promotion error',
        'detail': 'An internal promotion error occurred.',
    },
    PromoErrorCode.PROMO_BENEFIT_ACTIVE: {
        'http_status': 409,
        'message': 'Active benefit exists',
        'detail': 'This company already has an active promotion benefit.',
    },
}


class PaymentErrorCode(str, Enum):
    """Pagos."""

    PAY_GATEWAY_UNAVAILABLE   = 'PAY_001'  # No hay adapter de pagos disponible
    PAY_INVALID_TRANSITION    = 'PAY_002'  # Transición de estado del cargo no permitida
    PAY_CHARGE_NOT_FOUND      = 'PAY_003'  # Cargo no encontrado
    PAY_DUPLICATE_IDEMPOTENCY = 'PAY_004'  # Misma idempotency key con body distinto
    PAY_GATEWAY_REJECTED      = 'PAY_005'  # El proveedor rechazó el cargo
    PAY_WEBHOOK_INVALID       = 'PAY_006'  # Firma de webhook inválida
    PAY_PROVIDER_ERROR        = 'PAY_007'  # Error al comunicarse con el proveedor
    PAY_CURRENCY_NOT_ALLOWED  = 'PAY_008'  # Moneda no permitida para el país de la empresa
    PAY_CURRENCY_MISMATCH     = 'PAY_009'  # Moneda del refund distinta a la del cargo


PAY_REGISTRY: dict[PaymentErrorCode, dict] = {
    PaymentErrorCode.PAY_GATEWAY_UNAVAILABLE: {
        'http_status': 503,
        'message': 'Payment gateway unavailable',
        'detail': 'No payment provider is currently available. Check the SIMULATE_PAYMENT and PAYMENT_PROVIDER platform parameters.',
    },
    PaymentErrorCode.PAY_INVALID_TRANSITION: {
        'http_status': 409,
        'message': 'Invalid charge transition',
        'detail': 'The requested change of state for this charge is not allowed by the payment state machine.',
    },
    PaymentErrorCode.PAY_CHARGE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Charge not found',
        'detail': 'The requested charge does not exist.',
    },
    PaymentErrorCode.PAY_DUPLICATE_IDEMPOTENCY: {
        'http_status': 409,
        'message': 'Duplicate idempotency key',
        'detail': 'An operation with the same idempotency key but different payload was already processed.',
    },
    PaymentErrorCode.PAY_GATEWAY_REJECTED: {
        'http_status': 402,
        'message': 'Payment rejected',
        'detail': 'The payment provider rejected the charge.',
    },
    PaymentErrorCode.PAY_WEBHOOK_INVALID: {
        'http_status': 400,
        'message': 'Invalid webhook signature',
        'detail': 'The signature of the incoming webhook could not be verified.',
    },
    PaymentErrorCode.PAY_PROVIDER_ERROR: {
        'http_status': 502,
        'message': 'Payment provider error',
        'detail': 'An error occurred while communicating with the payment provider.',
    },
    PaymentErrorCode.PAY_CURRENCY_NOT_ALLOWED: {
        'http_status': 400,
        'message': 'Charge currency not allowed',
        'detail': 'The charge currency is not allowed for the company country.',
    },
    PaymentErrorCode.PAY_CURRENCY_MISMATCH: {
        'http_status': 400,
        'message': 'Currency mismatch',
        'detail': 'The currency does not match the charge or invoice currency for this operation.',
    },
}

class ComplementErrorCode(str, Enum):
    """Complementos contratados por empresa."""

    CMP_OFFERING_MISMATCH = 'CMP_001'  # Plan/complemento no cuadra con la modalidad
    CMP_NOT_ON_PLAN = 'CMP_002'  # Un complemento no entra en el plan
    CMP_OFFERING_LOCKED = 'CMP_003'  # No se cambia la contratación con vínculos
    CMP_NOT_AVAILABLE = 'CMP_004'  # No es un complemento activo
    CMP_ALREADY_ACTIVE = 'CMP_005'  # La empresa ya tiene la licencia activa
    CMP_NOT_FOUND = 'CMP_006'  # Licencia inexistente
    CMP_NOT_ACTIVE = 'CMP_007'  # La licencia no está activa
    CMP_SERVICE_REQUIRED = 'CMP_008'  # El complemento de suscripción exige servicio


CMP_REGISTRY: dict[ComplementErrorCode, dict] = {
    ComplementErrorCode.CMP_OFFERING_MISMATCH: {
        'http_status': 400,
        'message': 'Offering and billing mode do not match',
        'detail': 'A plan functionality must be included. A complement must be renewal or one-time.',
    },
    ComplementErrorCode.CMP_NOT_ON_PLAN: {
        'http_status': 409,
        'message': 'Complement cannot be added to a plan',
        'detail': 'This functionality is sold as a complement and cannot be included in a subscription plan.',
    },
    ComplementErrorCode.CMP_OFFERING_LOCKED: {
        'http_status': 409,
        'message': 'Commercial offering is locked',
        'detail': 'The offering cannot change while the functionality is on a plan or has an active company license.',
    },
    ComplementErrorCode.CMP_NOT_AVAILABLE: {
        'http_status': 400,
        'message': 'Complement not available',
        'detail': 'That functionality is not an active complement.',
    },
    ComplementErrorCode.CMP_ALREADY_ACTIVE: {
        'http_status': 409,
        'message': 'Complement already active',
        'detail': 'This company already has an active license for that complement.',
    },
    ComplementErrorCode.CMP_NOT_FOUND: {
        'http_status': 404,
        'message': 'Complement license not found',
        'detail': 'The requested complement license does not exist.',
    },
    ComplementErrorCode.CMP_NOT_ACTIVE: {
        'http_status': 409,
        'message': 'Complement license is not active',
        'detail': 'Only an active complement license can be revoked.',
    },
    ComplementErrorCode.CMP_SERVICE_REQUIRED: {
        'http_status': 400,
        'message': 'Catalog service is required',
        'detail': 'A complement added to the subscription needs an active Neurana catalog service that carries the price.',
    },
}


__all__ = [
    'SubscriptionErrorCode',
    'RefundErrorCode',
    'SubscriptionLimitErrorCode',
    'InvoiceErrorCode',
    'PromoErrorCode',
    'PaymentErrorCode',
    'ComplementErrorCode',
    'SUB_REGISTRY',
    'RFD_REGISTRY',
    'SLIMIT_REGISTRY',
    'INV_REGISTRY',
    'PROMO_REGISTRY',
    'PAY_REGISTRY',
    'CMP_REGISTRY',
]
