"""
Esquemas de dominio del sistema de incidencias.

``TransactionLogEntry`` es la unidad de captura: UNA petición completa
(Solicitud + Proceso interno + Respuesta). El anillo por sesión mantiene las
últimas N de estas entradas.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

IncidentKind = Literal['incident', 'suggestion']
AttachmentKind = Literal['image', 'gif', 'video']


class IncidentAttachment(BaseModel):
    """Metadatos de un archivo de evidencia almacenado en object storage."""
    id: str
    object_name: str
    name: str = Field(max_length=255)
    content_type: str
    size: int = Field(ge=0)
    kind: AttachmentKind
    uploaded_at: str

    model_config = ConfigDict(extra='ignore')


class IncidentAttachmentView(BaseModel):
    """Adjunto expuesto al admin (sin ruta interna; URL firmada efímera)."""
    id: str
    name: str
    content_type: str
    size: int
    kind: AttachmentKind
    uploaded_at: str
    url: str = ''


class AttachmentUpload(BaseModel):
    """Archivo recibido del cliente, ya leído en memoria (validado aparte)."""
    name: str
    content_type: str
    data: bytes


class IncidentModuleRef(BaseModel):
    id: str
    code: str = ''
    name: str = ''


class IncidentFunctionalityRef(BaseModel):
    id: str
    key: str = ''
    label: str = ''


class IncidentCreate(BaseModel):
    """Datos de entrada para crear una incidencia (armados desde el draft)."""
    token: str
    kind: IncidentKind = 'incident'
    trace_id: str = ''
    severity: str = 'high'
    schema_name: str = ''
    company_id: str = ''
    module_id: str = ''
    functionality_id: str = ''
    page_section: str = ''
    reporter_user_id: str = ''
    reporter_username: str = ''
    reporter_email: str = ''
    error: dict = Field(default_factory=dict)
    snapshot: dict = Field(default_factory=dict)
    user_comment: str = ''


class IncidentView(BaseModel):
    """Vista de lectura de una incidencia (desacoplada del ORM)."""
    id: str
    code: str
    kind: IncidentKind = 'incident'
    status: str
    severity: str
    schema_name: str = ''
    company_id: str = ''
    reporter_user_id: str = ''
    reporter_username: str = ''
    reporter_email: str = ''
    trace_id: str = ''
    module: Optional[IncidentModuleRef] = None
    functionality: Optional[IncidentFunctionalityRef] = None
    page_section: str = ''
    error: dict = Field(default_factory=dict)
    snapshot: dict = Field(default_factory=dict)
    user_comment: str = ''
    attachments: list[IncidentAttachment] = Field(default_factory=list)
    assigned_admin_id: str = ''
    resolution_notes: str = ''
    created_at: Optional[str] = None
    reported_at: Optional[str] = None
    resolved_at: Optional[str] = None


class TransactionLogEntry(BaseModel):
    """Una petición completa capturada para el contexto de una incidencia."""

    request_id: str
    ts: str
    origin: str = ''
    module_id: str = ''
    module_code: str = ''
    functionality_id: str = ''
    page_section: str = ''
    feature_key: str = ''
    method: str = ''
    path: str = ''
    query: Optional[str] = None
    request_body: str = '-'
    status: Optional[int] = None
    response_body: str = '-'
    duration_ms: Optional[float] = None
    logs: list[str] = Field(default_factory=list)

    model_config = {'from_attributes': True}


class BrowserConsoleEntry(BaseModel):
    ts: str = ''
    level: str = 'log'
    message: str = ''


class FrontendEvent(BaseModel):
    ts: str = ''
    type: str = ''
    summary: str = ''
    request_id: str = ''
    correlation_id: str = ''

    model_config = ConfigDict(extra='ignore')


class FrontendApiActivityEntry(BaseModel):
    ts: str = ''
    method: str = ''
    endpoint: str = ''
    status: Optional[int] = None
    duration_ms: Optional[int] = None
    request_id: str = ''
    correlation_id: str = ''
    result: str = ''
    error_summary: str = ''

    model_config = ConfigDict(extra='ignore')


class FrontendContextSnapshot(BaseModel):
    """Client-side technical context frozen at incident report time."""

    captured_at: str = ''
    application: dict = Field(default_factory=dict)
    navigation: dict = Field(default_factory=dict)
    browser: dict = Field(default_factory=dict)
    device: dict = Field(default_factory=dict)
    network: dict = Field(default_factory=dict)
    recent_events: list[FrontendEvent] = Field(default_factory=list)
    recent_api_activity: list[FrontendApiActivityEntry] = Field(default_factory=list)
    runtime: dict = Field(default_factory=dict)
    ui: dict = Field(default_factory=dict)
    session: dict = Field(default_factory=dict)
    browser_console: list[BrowserConsoleEntry] = Field(default_factory=list)
    correlation_id: str = ''
    trace_id: str = ''
    truncated: bool = False

    model_config = ConfigDict(extra='ignore')
