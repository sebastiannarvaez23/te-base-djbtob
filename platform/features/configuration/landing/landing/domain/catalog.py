"""Fixed catalog of landing page sections.

Keys are the public contract shared by admin UI and base-landing-web.
Order matches the home page layout.
"""

from typing import TypedDict


class LandingSectionDef(TypedDict):
    key: str
    sort_order: int
    label_es: str
    label_en: str


LANDING_SECTION_CATALOG: tuple[LandingSectionDef, ...] = (
    {'key': 'hero', 'sort_order': 1, 'label_es': 'Inicio', 'label_en': 'Home'},
    {
        'key': 'trust',
        'sort_order': 2,
        'label_es': 'Operadores logísticos confían en la base',
        'label_en': 'Logistics operators trust the base',
    },
    {
        'key': 'features',
        'sort_order': 3,
        'label_es': 'Por qué la base',
        'label_en': 'Why the base',
    },
    {
        'key': 'ai',
        'sort_order': 4,
        'label_es': 'Inteligencia artificial',
        'label_en': 'Artificial intelligence',
    },
    {
        'key': 'modules',
        'sort_order': 5,
        'label_es': 'Módulos del WMS',
        'label_en': 'WMS modules',
    },
    {
        'key': 'pda',
        'sort_order': 6,
        'label_es': 'App nativa para PDA',
        'label_en': 'Native PDA app',
    },
    {
        'key': 'how',
        'sort_order': 7,
        'label_es': 'Cómo funciona',
        'label_en': 'How it works',
    },
    {'key': 'pricing', 'sort_order': 8, 'label_es': 'Planes', 'label_en': 'Plans'},
    {
        'key': 'testimonials',
        'sort_order': 9,
        'label_es': 'Testimonios',
        'label_en': 'Testimonials',
    },
    {
        'key': 'faq',
        'sort_order': 10,
        'label_es': 'Preguntas frecuentes',
        'label_en': 'FAQ',
    },
    {
        'key': 'gift',
        'sort_order': 11,
        'label_es': 'Para regalar',
        'label_en': 'Gift voucher',
    },
    {
        'key': 'cta',
        'sort_order': 12,
        'label_es': 'CTA final',
        'label_en': 'Final CTA',
    },
)

LANDING_SECTION_KEYS: frozenset[str] = frozenset(s['key'] for s in LANDING_SECTION_CATALOG)

# Keys that map to existing landing header anchors (do not invent new nav items).
LANDING_NAV_SECTION_KEYS: frozenset[str] = frozenset({
    'features', 'ai', 'modules', 'pda', 'pricing', 'faq',
})
