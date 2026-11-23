"""Códigos de error — handbook (documentación de plataforma)."""
from enum import Enum


class HandbookErrorCode(str, Enum):
    """Manual / documentación de plataforma."""

    HBK_NOT_FOUND = 'HBK_001'
    HBK_FORBIDDEN = 'HBK_002'
    HBK_MANAGE_FORBIDDEN = 'HBK_003'
    HBK_INVALID_AUDIENCE = 'HBK_004'
    HBK_INVALID_KIND = 'HBK_005'
    HBK_REASON_REQUIRED = 'HBK_006'
    HBK_NOT_PENDING = 'HBK_007'
    HBK_PROPOSE_FORBIDDEN = 'HBK_008'
    HBK_APPROVE_FORBIDDEN = 'HBK_009'
    HBK_PENDING_EXISTS = 'HBK_010'
    HBK_SLUG_TAKEN = 'HBK_011'
    HBK_INVALID_VERSION = 'HBK_012'
    HBK_HIERARCHY_CYCLE = 'HBK_013'
    HBK_FEATURE_INVALID = 'HBK_014'
    HBK_MARKDOWN_INVALID = 'HBK_015'
    HBK_INVALID_LOCALE = 'HBK_016'
    HBK_INVALID_SLUG = 'HBK_017'
    HBK_DRAFT_REQUIRED = 'HBK_018'
    HBK_MENU_TITLE_REQUIRED = 'HBK_019'
    HBK_DELETE_ROOT = 'HBK_020'
    HBK_HAS_CHILDREN = 'HBK_021'
    HBK_HTTP_METHOD_REQUIRED = 'HBK_022'


HBK_REGISTRY: dict[HandbookErrorCode, dict] = {
    HandbookErrorCode.HBK_NOT_FOUND: {
        'http_status': 404,
        'message': 'Handbook content not available',
        'detail': 'That handbook topic is not available.',
    },
    HandbookErrorCode.HBK_FORBIDDEN: {
        'http_status': 403,
        'message': 'Handbook access denied',
        'detail': 'Your role or plan does not include this handbook topic.',
    },
    HandbookErrorCode.HBK_MANAGE_FORBIDDEN: {
        'http_status': 403,
        'message': 'Handbook management denied',
        'detail': 'Only a platform technology administrator or the platform administrator can open the handbook editor.',
    },
    HandbookErrorCode.HBK_INVALID_AUDIENCE: {
        'http_status': 400,
        'message': 'Invalid handbook audience',
        'detail': 'Audience must be public, admin or wms.',
    },
    HandbookErrorCode.HBK_INVALID_KIND: {
        'http_status': 400,
        'message': 'Invalid handbook kind',
        'detail': 'Kind must be manual, architecture, technical, plan, vision or api.',
    },
    HandbookErrorCode.HBK_REASON_REQUIRED: {
        'http_status': 400,
        'message': 'Change reason required',
        'detail': 'Explain why this handbook change is needed before sending it for approval.',
    },
    HandbookErrorCode.HBK_NOT_PENDING: {
        'http_status': 409,
        'message': 'Change request is not pending',
        'detail': 'Only a pending handbook change can be approved or rejected.',
    },
    HandbookErrorCode.HBK_PROPOSE_FORBIDDEN: {
        'http_status': 403,
        'message': 'Handbook proposal denied',
        'detail': 'Only a platform technology administrator can propose handbook changes.',
    },
    HandbookErrorCode.HBK_APPROVE_FORBIDDEN: {
        'http_status': 403,
        'message': 'Handbook approval denied',
        'detail': 'Only the platform administrator can approve or reject handbook changes.',
    },
    HandbookErrorCode.HBK_PENDING_EXISTS: {
        'http_status': 409,
        'message': 'A pending change already exists',
        'detail': 'This handbook page already has a change waiting for approval.',
    },
    HandbookErrorCode.HBK_SLUG_TAKEN: {
        'http_status': 409,
        'message': 'Handbook slug already exists',
        'detail': 'Another handbook page already uses that slug.',
    },
    HandbookErrorCode.HBK_INVALID_VERSION: {
        'http_status': 400,
        'message': 'Invalid handbook version',
        'detail': 'The content of a published language version changed. Raise its version number (for example, from 1.0 to 1.1) to save it.',
    },
    HandbookErrorCode.HBK_HIERARCHY_CYCLE: {
        'http_status': 400,
        'message': 'Invalid handbook hierarchy',
        'detail': 'A page cannot be placed under itself or under one of its descendants.',
    },
    HandbookErrorCode.HBK_FEATURE_INVALID: {
        'http_status': 400,
        'message': 'Invalid handbook feature',
        'detail': (
            'The selected functionality is not active for that audience, '
            'or does not match this page type (API pages require an API permission).'
        ),
    },
    HandbookErrorCode.HBK_MARKDOWN_INVALID: {
        'http_status': 400,
        'message': 'Invalid handbook markdown',
        'detail': 'The markdown file must be UTF-8 text within the size limit.',
    },
    HandbookErrorCode.HBK_INVALID_LOCALE: {
        'http_status': 400,
        'message': 'Invalid handbook locale',
        'detail': 'Locale must be es or en.',
    },
    HandbookErrorCode.HBK_INVALID_SLUG: {
        'http_status': 400,
        'message': 'Invalid handbook slug',
        'detail': 'Slug must use lowercase letters, numbers and hyphens.',
    },
    HandbookErrorCode.HBK_DRAFT_REQUIRED: {
        'http_status': 409,
        'message': 'Handbook draft required',
        'detail': 'Save a draft before sending the page for approval.',
    },
    HandbookErrorCode.HBK_MENU_TITLE_REQUIRED: {
        'http_status': 400,
        'message': 'Handbook menu name required',
        'detail': 'A page without content needs a menu name so its child pages can be grouped under it.',
    },
    HandbookErrorCode.HBK_DELETE_ROOT: {
        'http_status': 400,
        'message': 'Top-level handbook page stays',
        'detail': 'Top-level handbook pages stay in the manual. Delete the pages nested under them.',
    },
    HandbookErrorCode.HBK_HAS_CHILDREN: {
        'http_status': 409,
        'message': 'Handbook page still groups other pages',
        'detail': 'This page still groups other pages. Delete those nested pages first.',
    },
    HandbookErrorCode.HBK_HTTP_METHOD_REQUIRED: {
        'http_status': 400,
        'message': 'API page needs an HTTP method',
        'detail': 'An API page needs its HTTP method (GET, POST, PUT, PATCH or DELETE) to show it in the menu.',
    },
}

__all__ = ['HandbookErrorCode', 'HBK_REGISTRY']
