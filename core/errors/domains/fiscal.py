"""Forwarded Neurana fiscal codes (FIS_*) for base toasts when the remote envelope is passed through."""
from enum import Enum


class FisErrorCode(str, Enum):
    FIS_ISSUER_NOT_CONFIGURED = 'FIS_001'
    FIS_ISSUER_INVALID = 'FIS_002'
    FIS_DOCUMENT_INVALID = 'FIS_003'
    FIS_TRANSMITTER_UNAVAILABLE = 'FIS_004'
    FIS_SUBMISSION_NOT_FOUND = 'FIS_005'
    FIS_SUBMISSION_NOT_RETRYABLE = 'FIS_006'
    FIS_CREDIT_NOTE_NOT_FOUND = 'FIS_007'
    FIS_RESOLUTION_NOT_VALID = 'FIS_008'
    FIS_JURISDICTION_UNKNOWN = 'FIS_009'


FIS_REGISTRY: dict[FisErrorCode, dict] = {
    FisErrorCode.FIS_ISSUER_NOT_CONFIGURED: {
        'http_status': 422,
        'message': 'Issuer fiscal profile not configured',
        'detail': 'Complete the issuer fiscal profile (tax id, address, software) before issuing electronic documents.',
    },
    FisErrorCode.FIS_ISSUER_INVALID: {
        'http_status': 422,
        'message': 'Issuer fiscal profile is invalid',
        'detail': 'The issuer fiscal profile does not meet the tax authority rules. Review the listed fields.',
    },
    FisErrorCode.FIS_DOCUMENT_INVALID: {
        'http_status': 422,
        'message': 'Fiscal document is invalid',
        'detail': 'The document does not meet the tax authority rules. Review the listed issues and try again.',
    },
    FisErrorCode.FIS_TRANSMITTER_UNAVAILABLE: {
        'http_status': 503,
        'message': 'Tax authority channel unavailable',
        'detail': 'The configured channel to the tax authority is not available yet. Documents stay queued.',
    },
    FisErrorCode.FIS_SUBMISSION_NOT_FOUND: {
        'http_status': 404,
        'message': 'Fiscal submission not found',
        'detail': 'No submission to the tax authority matches the given identifier.',
    },
    FisErrorCode.FIS_SUBMISSION_NOT_RETRYABLE: {
        'http_status': 409,
        'message': 'Fiscal submission cannot be retried',
        'detail': 'Only failed submissions can be sent again to the tax authority.',
    },
    FisErrorCode.FIS_CREDIT_NOTE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Credit note not found',
        'detail': 'No credit note matches the given identifier.',
    },
    FisErrorCode.FIS_RESOLUTION_NOT_VALID: {
        'http_status': 422,
        'message': 'Numbering resolution not valid today',
        'detail': 'The active numbering resolution for this document type is outside its validity dates.',
    },
    FisErrorCode.FIS_JURISDICTION_UNKNOWN: {
        'http_status': 500,
        'message': 'Unknown fiscal jurisdiction',
        'detail': 'FISCAL_JURISDICTION does not match any supported country.',
    },
}
