"""Unit tests for welcome inbox notifications."""
import uuid
from contextlib import nullcontext
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.communication.messaging.inbox.application.welcome_notifier import (
    notify_collaborator_welcome,
    notify_executive_welcome,
)
from client.features.communication.messaging.inbox.domain.enums import ActorKind, NotificationKind
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel


class TestWelcomeNotifier(TestCase):

    @patch('client.features.communication.messaging.inbox.application.welcome_notifier.NotificationManagerFactory')
    @patch('client.features.communication.messaging.inbox.application.welcome_notifier.schema_context', lambda s: nullcontext())
    def test_executive_welcome_delivers_success_notification(self, MockFactory):
        manager = MagicMock()
        MockFactory.create.return_value = manager
        user_id = uuid.uuid4()

        notify_executive_welcome(
            schema_name='acme',
            user_id=user_id,
            user_name='Ana Pérez',
            company_name='ACME SAS',
        )

        manager.deliver.assert_called_once()
        schema_name, payload, recipients = manager.deliver.call_args.args
        self.assertEqual(schema_name, 'acme')
        self.assertEqual(recipients, [user_id])
        self.assertEqual(payload.kind, NotificationKind.ADMIN_DIRECT)
        self.assertEqual(payload.actor_kind, ActorKind.SYSTEM)
        self.assertEqual(payload.level, NotificationLevel.SUCCESS)
        self.assertEqual(payload.title, 'Bienvenido a la base!')
        self.assertIn('ACME SAS', payload.body)
        self.assertIn('Ana Pérez', payload.body)

    @patch('client.features.communication.messaging.inbox.application.welcome_notifier.NotificationManagerFactory')
    @patch('client.features.communication.messaging.inbox.application.welcome_notifier.schema_context', lambda s: nullcontext())
    def test_collaborator_welcome_delivers_success_notification(self, MockFactory):
        manager = MagicMock()
        MockFactory.create.return_value = manager
        user_id = uuid.uuid4()

        notify_collaborator_welcome(
            schema_name='acme',
            user_id=user_id,
            user_name='Luis Gómez',
            company_name='ACME SAS',
        )

        manager.deliver.assert_called_once()
        _, payload, recipients = manager.deliver.call_args.args
        self.assertEqual(recipients, [user_id])
        self.assertEqual(payload.title, 'Bienvenido al equipo')
        self.assertIn('colaborador', payload.body)
        self.assertIn('Luis Gómez', payload.body)
