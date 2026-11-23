"""
Ejecuta la suite golden del harness IA.

Uso:
    python manage.py run_ai_evals
    python manage.py run_ai_evals --persist
"""

from django.core.management.base import BaseCommand

from core.ai.evals import run_harness_evals


class Command(BaseCommand):
    help = 'Run offline harness AI evals (facts gate, parse, router, capability).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--persist',
            action='store_true',
            help='Persist the suite result in the public schema (ai_eval_suite_runs).',
        )

    def handle(self, *args, **options):
        result = run_harness_evals()
        if options.get('persist'):
            from platform.features.configuration.ai.evals.infrastructure.repositories import (
                DjangoEvalSuiteRepository,
            )
            saved = DjangoEvalSuiteRepository().save(result)
            self.stdout.write(self.style.SUCCESS(
                f'persisted suite {saved.id} passed={saved.passed} failed={saved.failed}',
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'suite harness passed={result.passed} failed={result.failed}',
            ))
        for case in result.cases:
            mark = 'PASS' if case.passed else 'FAIL'
            line = f'  [{mark}] {case.key}: {case.description}'
            if case.detail:
                line += f' ({case.detail})'
            style = self.style.SUCCESS if case.passed else self.style.ERROR
            self.stdout.write(style(line))
        if result.failed:
            raise SystemExit(1)
