"""Plantilla Excel para importación de locaciones (país / depto / ciudad)."""

from __future__ import annotations

import io

from openpyxl import Workbook

from platform.features.geography.location.location.application.import_use_cases import TEMPLATE_HEADERS


class LocationImportTemplateFile:
    def __init__(self, *, filename: str, content: bytes):
        self.filename = filename
        self.content_type = (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.content = content


SAMPLE_ROWS = (
    ('CO', 'Colombia', 'ANT', 'Antioquia', 'MED', 'Medellín', '6.244200', '-75.581200', 'true'),
    ('CO', 'Colombia', 'CUN', 'Cundinamarca', 'BOG', 'Bogotá', '4.711000', '-74.072100', 'true'),
)


def build_location_import_template() -> LocationImportTemplateFile:
    wb = Workbook()
    ws = wb.active
    ws.title = 'locations'
    ws.append(list(TEMPLATE_HEADERS))
    for row in SAMPLE_ROWS:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return LocationImportTemplateFile(
        filename='locations_import_template.xlsx',
        content=buffer.getvalue(),
    )
