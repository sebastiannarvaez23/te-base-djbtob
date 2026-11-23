"""Functionality categories of the tenant catalog.

``api`` functionalities are the permissions an Integration Application can be
granted (OAuth scopes); they never appear as UI features.
"""
from __future__ import annotations

FEATURES_CATEGORY = 'features'
AI_CATEGORY = 'ai'
API_CATEGORY = 'api'

FUNCTIONALITY_CATEGORIES: tuple[str, ...] = (FEATURES_CATEGORY, AI_CATEGORY, API_CATEGORY)
