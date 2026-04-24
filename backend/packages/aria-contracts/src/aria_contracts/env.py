"""OpenEnv-facing contracts for the ARIA environment.

Subclasses OpenEnv's Action / Observation / State base classes (which are
Pydantic models with `extra="forbid"`), so every field must be declared.

The hackathon README describes a "Discrete(15)" action space and a Dict
observation. OpenEnv doesn't use gymnasium's space objects directly — we
express the same shape with Pydantic. See OPENENV_API_NOTES.md in env-service.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Any, Literal

from openenv.core.env_server.types import Action, Observation, State
from pydantic import BaseModel, ConfigDict, Field

from aria_contracts.reward import RewardBreakdown

# =============================================================================
# Action space — 15 discrete actions
# =============================================================================


class ActionId(IntEnum):
    """The 15 ARIA actions. Integer IDs are stable across versions."""

    SEND_MSG = 0
    SCHEDULE = 1
    RESCHEDULE = 2
    CANCEL = 3
    DELEGATE = 4
    DRAFT_REPLY = 5
    SET_REMINDER = 6
    PURCHASE = 7
    RESOLVE_CONFLICT = 8
    ASK_USER = 9
    DECLINE_INVITE = 10
    PROPOSE_ALTERNATIVE = 11
    BATCH_ACTION = 12
    WAIT = 13
    ESCALATE = 14


NUM_ACTIONS: int = len(ActionId)  # 15


class AriaAction(Action):
    """A single action taken by the agent.

    `action_id` is required; `target_id` and `payload` are action-dependent.
    Handlers validate payload shape — the contract stays loose so new action
    variants don't require a contract bump.
    """

    action_id: int = Field(ge=0, le=NUM_ACTIONS - 1)
    target_id: str | None = Field(
        default=None,
        description="Entity this action targets: event_id, contact_id, email_id, task_id, etc.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters (e.g. new_time, message_body).",
    )


# =============================================================================
# Observation sub-models
# =============================================================================


Location = Literal["home", "office", "commute", "other"]


class CalendarEvent(BaseModel):
    """A single calendar event. Agents see upcoming 30 days."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    day_offset: int = Field(ge=0, le=29, description="Days from episode start")
    start_hour: float = Field(ge=0.0, lt=24.0)
    end_hour: float = Field(gt=0.0, le=24.0)
    title: str
    priority: float = Field(ge=0.0, le=1.0)
    flexibility: float = Field(
        ge=0.0, le=1.0, description="0 = rigid, 1 = freely reschedulable"
    )
    participant_ids: list[str] = Field(default_factory=list)
    location: Location = "other"


class InboxItem(BaseModel):
    """A message in the priority inbox."""

    model_config = ConfigDict(extra="forbid")

    email_id: str
    sender_id: str
    subject: str
    urgency: float = Field(ge=0.0, le=1.0)
    age_hours: float = Field(ge=0.0)
    requires_reply: bool = True
    sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)


class RelationshipNode(BaseModel):
    """One contact in the relationship graph."""

    model_config = ConfigDict(extra="forbid")

    contact_id: str
    name: str
    relationship_kind: Literal[
        "boss", "report", "partner", "family", "friend", "colleague", "vendor", "other"
    ]
    closeness: float = Field(
        ge=0.0, le=1.0, description="Strength of relationship; decays with neglect."
    )
    trust: float = Field(ge=0.0, le=1.0, default=0.5)
    last_contact_hours: float = Field(ge=0.0)
    tone_preference: Literal["formal", "casual", "warm", "direct"] = "casual"


class PendingTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    title: str
    priority: float = Field(ge=0.0, le=1.0)
    deadline_hours: float = Field(
        description="Hours until deadline; negative = overdue."
    )
    estimated_minutes: int = Field(ge=0)
    delegatable: bool = False
    assignee_id: str | None = None
    status: Literal["open", "assigned", "done", "blocked"] = "open"


# =============================================================================
# Observation
# =============================================================================


ScenarioCategory = Literal[
    "calendar_conflict",
    "email_triage",
    "message_reply",
    "dinner_planning",
    "delegation",
    "shopping",
]

Difficulty = Literal["easy", "medium", "hard"]


class AriaObservation(Observation):
    """Observation returned by AriaEnv.step() and AriaEnv.reset().

    Inherits `done`, `reward`, `metadata` from OpenEnv's Observation base.
    """

    # --- world state the agent sees ---
    time: float = Field(
        ge=0.0,
        le=24.0,
        description="Hours since episode start (episode covers one day).",
    )
    location: Location = "home"
    calendar: list[CalendarEvent] = Field(default_factory=list)
    inbox: list[InboxItem] = Field(
        default_factory=list, description="Priority-ordered, highest first."
    )
    relationships: list[RelationshipNode] = Field(default_factory=list)
    pending_tasks: list[PendingTask] = Field(default_factory=list)
    preferences: list[float] = Field(
        default_factory=lambda: [0.0] * 64,
        min_length=64,
        max_length=64,
        description="Learned preference vector (length 64).",
    )

    # --- scenario context ---
    scenario_category: ScenarioCategory | None = None
    difficulty: Difficulty | None = None

    # --- affordances exposed for convenience ---
    step_count: int = Field(ge=0, default=0)
    max_steps: int = Field(ge=1, default=50)

    # --- multi-dim reward is exposed in metadata too, for introspection ---
    reward_breakdown: RewardBreakdown | None = None


# =============================================================================
# State
# =============================================================================


class AriaState(State):
    """Full environment state — includes hidden variables for grading/debug."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    scenario_category: ScenarioCategory
    difficulty: Difficulty
    seed: int
    max_steps: int = 50
    reward_so_far: RewardBreakdown
    # hidden variables for judges to inspect:
    hidden: dict[str, Any] = Field(default_factory=dict)
