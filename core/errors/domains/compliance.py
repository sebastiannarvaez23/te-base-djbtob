"""Códigos de error — compliance / políticas."""
from enum import Enum


class PolicyErrorCode(str, Enum):
    """Políticas legales / acuerdos (platform compliance)."""

    POLICY_NOT_FOUND           = 'POL_001'
    POLICY_DUPLICATE_CODE      = 'POL_002'
    POLICY_COUNTRY_NOT_FOUND   = 'POL_003'
    POLICY_EMPTY_MARKDOWN      = 'POL_004'
    POLICY_INVALID_COUNTRY     = 'POL_005'
    POLICY_STORAGE_ERROR       = 'POL_006'
    POLICY_ALREADY_SIGNED      = 'POL_007'
    POLICY_INACTIVE            = 'POL_008'
    POLICY_AUDIENCE_MISMATCH   = 'POL_009'
    POLICY_SIGNATURE_NOT_FOUND = 'POL_010'
    POLICY_CONTENT_TAMPERED    = 'POL_011'
    POLICY_SIGNATURE_INVALID   = 'POL_012'
    POLICY_HAS_SIGNATURES      = 'POL_013'
    POLICY_COUNTRY_REVOKED     = 'POL_014'
    POLICY_DRAFT_NOT_FOUND     = 'POL_015'
    POLICY_DRAFT_EXISTS        = 'POL_016'
    POLICY_NOT_APPROVED        = 'POL_017'
    POLICY_NOT_SIGNABLE        = 'POL_018'
    POLICY_CHANGE_SUMMARY_REQUIRED = 'POL_019'
    POLICY_COUNTRY_MISMATCH = 'POL_020'


POL_REGISTRY: dict[PolicyErrorCode, dict] = {
    PolicyErrorCode.POLICY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Policy not found',
        'detail': 'The requested policy does not exist.',
    },
    PolicyErrorCode.POLICY_DUPLICATE_CODE: {
        'http_status': 409,
        'message': 'Duplicate policy code',
        'detail': 'A policy with that code already exists.',
    },
    PolicyErrorCode.POLICY_COUNTRY_NOT_FOUND: {
        'http_status': 404,
        'message': 'Policy country not found',
        'detail': 'The requested country variant of the policy does not exist.',
    },
    PolicyErrorCode.POLICY_EMPTY_MARKDOWN: {
        'http_status': 400,
        'message': 'Empty policy markdown',
        'detail': 'Policy markdown content cannot be empty.',
    },
    PolicyErrorCode.POLICY_INVALID_COUNTRY: {
        'http_status': 400,
        'message': 'Invalid policy country',
        'detail': 'The country must be an ISO 3166-1 alpha-2 code such as CO or US.',
    },
    PolicyErrorCode.POLICY_STORAGE_ERROR: {
        'http_status': 502,
        'message': 'Policy storage error',
        'detail': 'Could not read or write the policy markdown in object storage.',
    },
    PolicyErrorCode.POLICY_ALREADY_SIGNED: {
        'http_status': 409,
        'message': 'Policy already signed',
        'detail': 'This subject has already signed the current version of the policy.',
    },
    PolicyErrorCode.POLICY_INACTIVE: {
        'http_status': 409,
        'message': 'Policy inactive',
        'detail': 'Inactive policies cannot be signed.',
    },
    PolicyErrorCode.POLICY_AUDIENCE_MISMATCH: {
        'http_status': 403,
        'message': 'Policy audience mismatch',
        'detail': 'The signatory type does not match the policy audience.',
    },
    PolicyErrorCode.POLICY_SIGNATURE_NOT_FOUND: {
        'http_status': 404,
        'message': 'Policy signature not found',
        'detail': 'The requested policy signature does not exist.',
    },
    PolicyErrorCode.POLICY_CONTENT_TAMPERED: {
        'http_status': 409,
        'message': 'Policy content integrity error',
        'detail': 'The stored policy markdown does not match its registered content hash.',
    },
    PolicyErrorCode.POLICY_SIGNATURE_INVALID: {
        'http_status': 409,
        'message': 'Invalid policy signature',
        'detail': 'The digital seal of the policy signature could not be verified.',
    },
    PolicyErrorCode.POLICY_HAS_SIGNATURES: {
        'http_status': 409,
        'message': 'Policy has signatures',
        'detail': 'The policy or country variant cannot be deleted because digital signatures already exist.',
    },
    PolicyErrorCode.POLICY_COUNTRY_REVOKED: {
        'http_status': 409,
        'message': 'Policy version revoked',
        'detail': 'This policy country version was revoked and cannot be signed. Accept the current published version instead.',
    },
    PolicyErrorCode.POLICY_DRAFT_NOT_FOUND: {
        'http_status': 404,
        'message': 'Policy draft not found',
        'detail': 'There is no draft for this policy country. Start editing to create one.',
    },
    PolicyErrorCode.POLICY_DRAFT_EXISTS: {
        'http_status': 409,
        'message': 'Policy draft already exists',
        'detail': 'A draft already exists for this policy country. Continue editing or discard it first.',
    },
    PolicyErrorCode.POLICY_NOT_APPROVED: {
        'http_status': 409,
        'message': 'Policy version not approved',
        'detail': 'There is no approved version ready to release for this policy country.',
    },
    PolicyErrorCode.POLICY_NOT_SIGNABLE: {
        'http_status': 409,
        'message': 'Policy version not signable',
        'detail': 'Only the published version of a policy can be signed.',
    },
    PolicyErrorCode.POLICY_CHANGE_SUMMARY_REQUIRED: {
        'http_status': 400,
        'message': 'Change summary required',
        'detail': (
            'A summary of the changes is required when releasing an update '
            'to an already published policy country version.'
        ),
    },
    PolicyErrorCode.POLICY_COUNTRY_MISMATCH: {
        'http_status': 400,
        'message': 'Policy country mismatch',
        'detail': (
            'The policy country must match the company jurisdiction. '
            'Use the ISO country derived from the company location.'
        ),
    },
}

__all__ = ['PolicyErrorCode', 'POL_REGISTRY']
