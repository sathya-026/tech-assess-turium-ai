from enum import StrEnum

# StrEnum, not (str, Enum). With the mixin form, str(ItemStatus.INDEXED) returns
# "ItemStatus.INDEXED" rather than "indexed" — which silently writes enum reprs
# into the status and role columns, breaking both status filtering and memory
# replay. StrEnum makes str() return the value.


class AIProviderType(StrEnum):
    OPENAI = "openai"
    STUB = "stub"


class EmbeddingProviderType(StrEnum):
    OPENAI = "openai"
    STUB = "stub"


class MessageRole(StrEnum):
    """
    The only roles persisted. There is no "tool" role — this service has no
    tool calling, so a messages row maps 1:1 onto a MemoryMessage.
    """

    USER = "user"
    ASSISTANT = "assistant"


class ItemStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
