"""ARIA shared contracts — one import surface for every microservice.

Everything re-exported here is considered public API and subject to semver.
Version: 0.1.0
"""
from aria_contracts.env import (
    ActionId,
    AriaAction,
    AriaObservation,
    AriaState,
    CalendarEvent,
    Difficulty,
    InboxItem,
    Location,
    PendingTask,
    RelationshipNode,
    ScenarioCategory,
)
from aria_contracts.reward import (
    REWARD_WEIGHTS,
    RewardBreakdown,
)
from aria_contracts.voice import (
    TTSRequest,
    VoiceChunk,
    VoiceTranscript,
)
from aria_contracts.agent import (
    AgentTurnRequest,
    AgentTurnResponse,
    ToolCall,
)
from aria_contracts.memory import (
    MemoryHit,
    MemoryNamespace,
    MemoryQuery,
    MemoryWrite,
)
from aria_contracts.gateway import (
    GwAgentEvent,
    GwEventKind,
    GwSessionStart,
)

__version__ = "0.1.0"

__all__ = [
    "ActionId",
    "AgentTurnRequest",
    "AgentTurnResponse",
    "AriaAction",
    "AriaObservation",
    "AriaState",
    "CalendarEvent",
    "Difficulty",
    "GwAgentEvent",
    "GwEventKind",
    "GwSessionStart",
    "InboxItem",
    "Location",
    "MemoryHit",
    "MemoryNamespace",
    "MemoryQuery",
    "MemoryWrite",
    "PendingTask",
    "RelationshipNode",
    "REWARD_WEIGHTS",
    "RewardBreakdown",
    "ScenarioCategory",
    "TTSRequest",
    "ToolCall",
    "VoiceChunk",
    "VoiceTranscript",
    "__version__",
]
