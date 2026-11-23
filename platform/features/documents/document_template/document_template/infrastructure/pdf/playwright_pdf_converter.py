"""
PlaywrightPdfConverter — the only place that touches Playwright/Chromium.

Implements IPdfConverter by driving a headless Chromium instance: same
engine as the editor's live-preview iframe, so the PDF matches the preview.
No system-level native libraries are required (Playwright ships its own
browser binary, installed once with `playwright install chromium`).

Performance note: a fresh Chromium process is launched per call (~300-500ms
cold start). Acceptable for the admin's "download test" button; if bulk
invoice generation ever needs throughput, pool/reuse a browser context here
— the renderer never has to change.
"""
from __future__ import annotations

import asyncio
import sys

from core.errors import AppErrorCode, AppException

from ...domain.pdf_converter import IPdfConverter


def _ensure_windows_event_loop() -> None:
    """Playwright spawns Chromium via subprocess; SelectorEventLoop on Windows raises NotImplementedError."""
    if sys.platform != 'win32':
        return
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


class PlaywrightPdfConverter(IPdfConverter):

    def to_pdf(self, html: str, *, page_format: str, margin: str) -> bytes:
        _ensure_windows_event_loop()
        try:
            from playwright.sync_api import sync_playwright  # lazy: avoids import cost until needed
        except ImportError as exc:
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'Playwright not installed: {exc}',
            )

        try:
            with sync_playwright() as p:
                # --no-sandbox keeps Chromium happy when the backend runs as
                # root inside a container; harmless on a desktop host.
                browser = p.chromium.launch(args=['--no-sandbox'])
                try:
                    page = browser.new_page()
                    # The HTML is self-contained, so `load` is enough;
                    # `networkidle` would stall waiting on phantom requests.
                    page.set_content(html, wait_until='load')
                    return page.pdf(
                        format=page_format,
                        print_background=True,   # honour background colours from the template
                        margin={'top': margin, 'right': margin,
                                'bottom': margin, 'left': margin},
                    )
                finally:
                    browser.close()
        except AppException:
            raise
        except Exception as exc:
            # Most common cause: the Chromium binary was never installed
            # (`playwright install chromium`). Surface a clean DOC_RENDER_FAILED
            # instead of an opaque 500.
            raise AppException(
                AppErrorCode.DOC_RENDER_FAILED,
                override_detail=f'Chromium failed to produce PDF: {exc.__class__.__name__}: {exc}',
            )
