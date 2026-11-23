"""Motor de mapeo campo-a-campo."""

from __future__ import annotations

from typing import Any

from core.errors import AppErrorCode, ValidationAppException


def validate_mapping_rules(rules: list[dict[str, Any]]) -> None:
    if not isinstance(rules, list):
        raise ValidationAppException(
            AppErrorCode.INT_INVALID_MAPPING,
            override_detail='Mapping rules must be a list.',
        )
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict) or 'source' not in rule or 'target' not in rule:
            raise ValidationAppException(
                AppErrorCode.INT_INVALID_MAPPING,
                override_detail=f'Rule at index {idx} must have source and target.',
            )


def apply_mapping(rules: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    validate_mapping_rules(rules)
    result: dict[str, Any] = {}
    for rule in rules:
        value = source.get(rule['source'])
        if value is not None:
            result[rule['target']] = value
    return result


def reverse_mapping(rules: list[dict[str, Any]], internal: dict[str, Any]) -> dict[str, Any]:
    validate_mapping_rules(rules)
    reverse_rules = [{'source': r['target'], 'target': r['source']} for r in rules]
    return apply_mapping(reverse_rules, internal)
