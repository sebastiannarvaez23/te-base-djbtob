"""
core/realtime/groups.py
───────────────────────
Convención única de nombres de grupo del channel layer.

Se namespacea por ``schema`` para que dos tenants nunca compartan grupo,
de forma consistente con el inbox particionado por schema. Los nombres
respetan el charset válido de Channels (``[a-zA-Z0-9._-]``, < 100 chars):
los UUID (con guiones) y los schema names (alfanuméricos) encajan.
"""


class RealtimeGroups:
    PREFIX = 'rt'

    @classmethod
    def user(cls, schema: str, user_id) -> str:
        """Grupo personal de un usuario dentro de un tenant."""
        return f'{cls.PREFIX}.{schema}.user.{user_id}'

    @classmethod
    def company(cls, schema: str) -> str:
        """Grupo de todos los usuarios conectados de una empresa."""
        return f'{cls.PREFIX}.{schema}.company'

    @classmethod
    def platform_task_monitor(cls) -> str:
        """Grupo admin (schema público) para el monitor de tareas automatizadas."""
        return f'{cls.PREFIX}.platform.task_monitor'

    @classmethod
    def platform_live_logs(cls) -> str:
        """Grupo admin (schema público) para el stream de logs en vivo."""
        return f'{cls.PREFIX}.platform.live_logs'

    @classmethod
    def platform_support(cls) -> str:
        """Grupo admin (schema público) para la cola / tablero de support."""
        return f'{cls.PREFIX}.platform.support'
