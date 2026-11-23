from django.db import models

from core.ids import uuid7


class AiEvalSuiteRun(models.Model):
    """Resultado persistido de una suite de evals (schema público)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    suite = models.CharField(max_length=40, default='harness', db_index=True)
    passed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    cases = models.JSONField(default=list, blank=True)
    ran_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_eval_suite_runs'
        ordering = ['-ran_at']
        verbose_name = 'AI eval suite run'
