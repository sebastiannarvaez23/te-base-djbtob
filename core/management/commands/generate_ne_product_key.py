"""Generate the base's Ed25519 product key for Neurana ``private_key_jwt``.

    python manage.py generate_ne_product_key            # writes NE_PRODUCT_PRIVATE_KEY_FILE
    python manage.py generate_ne_product_key --force    # rotate (replaces the file)
    python manage.py generate_ne_product_key --show     # print the current public JWK

Register the printed public JWK in Neurana:

    python manage.py register_product_key --client-id <NE_PRODUCT_CLIENT_ID> --jwk '<json>'
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from necore.ecosystem.keys import (
    SigningKey,
    generate_private_key,
    load_private_key,
    private_key_to_pem,
)


class Command(BaseCommand):
    help = 'Generate (or show) the Ed25519 key the base uses to authenticate against Neurana.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Replace an existing key.')
        parser.add_argument('--show', action='store_true', help='Only print the current public JWK.')

    def handle(self, *args, force: bool, show: bool, **options):
        path = Path((getattr(settings, 'NE_PRODUCT_PRIVATE_KEY_FILE', '') or '').strip())
        if not str(path) or str(path) == '.':
            raise CommandError('NE_PRODUCT_PRIVATE_KEY_FILE is not configured.')

        if show or (path.is_file() and not force):
            if not path.is_file():
                raise CommandError(f'No key at {path}. Run without --show to create one.')
            key = SigningKey.from_private(load_private_key(path.read_text(encoding='ascii')))
            if not show:
                self.stdout.write(self.style.WARNING(f'Key already exists at {path} (use --force to rotate).'))
        else:
            private = generate_private_key()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(private_key_to_pem(private), encoding='ascii')
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            key = SigningKey.from_private(private)
            self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))

        jwk = json.dumps(key.to_jwk(), separators=(',', ':'))
        self.stdout.write(f'kid: {key.kid}')
        self.stdout.write(f'public JWK: {jwk}')
        client_id = getattr(settings, 'NE_PRODUCT_CLIENT_ID', '') or '<client-id>'
        self.stdout.write(
            'Register in Neurana:\n'
            f"  python manage.py register_product_key --client-id {client_id} --jwk '{jwk}'"
        )
