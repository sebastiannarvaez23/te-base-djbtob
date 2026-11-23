"""
PDF converter port.

Isolates the HTML→PDF engine (a volatile infrastructure detail) behind an
abstraction so the PDF *renderer* depends on a contract, not on a concrete
browser/library. This keeps the renderer's document-assembly logic pure and
unit-testable without launching a real engine.

Input is a self-contained HTML string; output is PDF bytes. No disk, no
storage — pure in-memory, same as the renderers.
"""
from abc import ABC, abstractmethod


class IPdfConverter(ABC):

    @abstractmethod
    def to_pdf(self, html: str, *, page_format: str, margin: str) -> bytes:
        """Convert `html` to PDF bytes.

        :param page_format: paper size as understood by the engine
                            (e.g. 'Letter', 'A4', 'Legal').
        :param margin:      uniform page margin as a CSS length (e.g. '16mm').
        """
        ...
