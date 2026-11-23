from core.errors.exceptions import AppException
from core.errors.codes import AppErrorCode
from platform.features.communication.email.email_sender.domain.interfaces import IEmailSenderRepository
from platform.features.communication.email.email_sender.domain.schemas import CreateEmailSenderSchema, UpdateEmailSenderSchema
from core.trace import trace_layer


class GetAllEmailSendersUseCase:
    def __init__(self, repo: IEmailSenderRepository):
        self.repo = repo
    @trace_layer('application')
    def execute(self, filters: dict | None = None):
        return self.repo.get_all(filters=filters)


class GetEmailSenderByIdUseCase:
    def __init__(self, repo: IEmailSenderRepository):
        self.repo = repo
    @trace_layer('application')
    def execute(self, sender_id):
        sender = self.repo.get_by_id(sender_id)
        if not sender:
            raise AppException(AppErrorCode.EMAIL_SENDER_NOT_FOUND, override_detail='Sender not found.')
        return sender


class CreateEmailSenderUseCase:
    def __init__(self, repo: IEmailSenderRepository):
        self.repo = repo
    @trace_layer('application')
    def execute(self, data: CreateEmailSenderSchema):
        existing = self.repo.get_by_code(data.code)
        if existing:
            raise AppException(AppErrorCode.EMAIL_SENDER_DUPLICATE, override_detail=f'Sender with code "{data.code}" already exists.')
        if data.is_default:
            self._clear_default()
        return self.repo.create(data.model_dump())
    def _clear_default(self):
        for s in self.repo.get_all():
            if s.is_default:
                self.repo.update(s, {'is_default': False})


class UpdateEmailSenderUseCase:
    def __init__(self, repo: IEmailSenderRepository):
        self.repo = repo
    @trace_layer('application')
    def execute(self, sender_id, data: UpdateEmailSenderSchema):
        sender = self.repo.get_by_id(sender_id)
        if not sender:
            raise AppException(AppErrorCode.EMAIL_SENDER_NOT_FOUND, override_detail='Sender not found.')
        changes = data.model_dump(exclude_none=True)
        if 'code' in changes and changes['code'] != sender.code:
            existing = self.repo.get_by_code(changes['code'])
            if existing:
                raise AppException(AppErrorCode.EMAIL_SENDER_DUPLICATE, override_detail=f'Sender with code "{changes["code"]}" already exists.')
        if changes.get('is_default'):
            for s in self.repo.get_all():
                if s.is_default and s.id != sender.id:
                    self.repo.update(s, {'is_default': False})
        return self.repo.update(sender, changes)


class DeleteEmailSenderUseCase:
    def __init__(self, repo: IEmailSenderRepository):
        self.repo = repo
    @trace_layer('application')
    def execute(self, sender_id):
        sender = self.repo.get_by_id(sender_id)
        if not sender:
            raise AppException(AppErrorCode.EMAIL_SENDER_NOT_FOUND, override_detail='Sender not found.')
        self.repo.delete(sender)
