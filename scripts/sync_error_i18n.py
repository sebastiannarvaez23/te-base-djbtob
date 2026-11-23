"""
Deprecated: usar el management command de Django.

    python manage.py syncerrors
    python manage.py syncerrors --dry-run

La lógica vive en ``core.errors.sync_i18n``.
"""
from __future__ import annotations

import sys


def main() -> None:
    print(
        'Este script fue reemplazado por el management command de Django.\n'
        'Usa:\n'
        '  python manage.py syncerrors\n'
        '  python manage.py syncerrors --dry-run',
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == '__main__':
    main()
