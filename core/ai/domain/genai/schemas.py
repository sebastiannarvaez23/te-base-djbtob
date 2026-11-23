"""
core/ai/domain/genai/schemas.py
────────────────────────────────
Contratos de entrada y salida (Pydantic) para los puertos GenAI.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class MessageRole(str, Enum):
    """Rol del emisor de un mensaje en una conversación con el modelo."""
    SYSTEM    = 'system'      # Instrucciones de comportamiento (se mapea a `system` del proveedor)
    USER      = 'user'        # Entrada del usuario / de la aplicación
    ASSISTANT = 'assistant'   # Respuesta previa del modelo (para dar contexto conversacional)


class FinishReason(str, Enum):
    """Motivo por el que el modelo terminó de generar."""
    STOP    = 'stop'          # Terminó normalmente
    LENGTH  = 'length'        # Se alcanzó el tope de tokens
    ERROR   = 'error'         # Falló (usado en degradación/fallback)
    UNKNOWN = 'unknown'


# ── Entrada ─────────────────────────────────────────────────────────────────

class Message(BaseModel):
    """Un turno de la conversación con el modelo."""
    role: MessageRole
    content: str

    @classmethod
    def user(cls, content: str) -> 'Message':
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> 'Message':
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def system(cls, content: str) -> 'Message':
        return cls(role=MessageRole.SYSTEM, content=content)


class ChatOptions(BaseModel):
    """Parámetros de generación. Valores None → el adaptador usa su default/settings."""
    model: Optional[str] = None                    # Override del modelo por llamada
    max_tokens: Optional[int] = None               # Tope de tokens de salida
    temperature: Optional[float] = None            # 0.0 = determinista, >0 = creativo
    timeout_seconds: Optional[float] = None         # Override del timeout por llamada
    metadata: dict = Field(default_factory=dict)   # Etiquetas libres para observabilidad


class Prompt(BaseModel):
    """Entrada completa para una generación de chat."""
    system: Optional[str] = None                   # Instrucción de sistema (opcional)
    messages: List[Message] = Field(default_factory=list)
    options: ChatOptions = Field(default_factory=ChatOptions)

    def with_system(self, text: str) -> 'Prompt':
        self.system = text
        return self


# ── Salida ──────────────────────────────────────────────────────────────────

class TokenUsage(BaseModel):
    """Consumo de tokens de una llamada. Base para observabilidad y FinOps."""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Completion(BaseModel):
    """Resultado de una generación de chat."""
    text: str
    model: str = ''
    provider: str = ''
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: FinishReason = FinishReason.STOP
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # True cuando el texto proviene de un fallback (proveedor caído/timeout),
    # no del modelo. Las features pueden decidir cómo señalarlo en la UI.
    degraded: bool = False


class EmbeddingResult(BaseModel):
    """Vector de embedding para un texto (búsqueda semántica / RAG)."""
    vector: List[float]
    model: str = ''
    provider: str = ''
    usage: TokenUsage = Field(default_factory=TokenUsage)


class ExtractionResult(BaseModel):
    """Resultado de extraer datos estructurados de un documento (cubo 2)."""
    data: dict = Field(default_factory=dict)       # Datos estructurados extraídos
    model: str = ''
    provider: str = ''
    usage: TokenUsage = Field(default_factory=TokenUsage)
    confidence: Optional[float] = None             # Confianza declarada por el modelo (si aplica)
    degraded: bool = False
