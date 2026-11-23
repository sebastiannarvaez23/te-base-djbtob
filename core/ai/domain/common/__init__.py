"""Shared AI domain helpers (capability tags, artifact refs)."""

from enum import Enum


class AiCapability(str, Enum):
    GENAI = 'genai'
    OPTIMIZATION = 'optimization'
    PREDICTIVE = 'predictive'
