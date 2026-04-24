/**
 * TypeScript mirrors of the `aria-contracts` Pydantic models.
 *
 * These must stay in lock-step with
 *   backend/packages/aria-contracts/src/aria_contracts/*.py
 * Field names use snake_case because Pydantic emits snake_case JSON.
 */

// ---------------------------------------------------------------------------
// Action space — 15 discrete actions
// ---------------------------------------------------------------------------

export const ActionId = {
  SEND_MSG: 0,
  SCHEDULE: 1,
  RESCHEDULE: 2,
  CANCEL: 3,
  DELEGATE: 4,
  DRAFT_REPLY: 5,
  SET_REMINDER: 6,
  PURCHASE: 7,
  RESOLVE_CONFLICT: 8,
  ASK_USER: 9,
  DECLINE_INVITE: 10,
  PROPOSE_ALTERNATIVE: 11,
  BATCH_ACTION: 12,
  WAIT: 13,
  ESCALATE: 14,
} as const;

export type ActionIdValue = (typeof ActionId)[keyof typeof ActionId];

export const NUM_ACTIONS: number = Object.keys(ActionId).length;

export interface AriaAction {
  action_id: number;
  target_id?: string | null;
  payload?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Observation sub-models
// ---------------------------------------------------------------------------

export type Location = "home" | "office" | "commute" | "other";

export interface CalendarEvent {
  event_id: string;
  day_offset: number;
  start_hour: number;
  end_hour: number;
  title: string;
  priority: number;
  flexibility: number;
  participant_ids: string[];
  location: Location;
}

export interface InboxItem {
  email_id: string;
  sender_id: string;
  subject: string;
  urgency: number;
  age_hours: number;
  requires_reply: boolean;
  sentiment: number;
}

export type RelationshipKind =
  | "boss"
  | "report"
  | "partner"
  | "family"
  | "friend"
  | "colleague"
  | "vendor"
  | "other";

export type TonePreference = "formal" | "casual" | "warm" | "direct";

export interface RelationshipNode {
  contact_id: string;
  name: string;
  relationship_kind: RelationshipKind;
  closeness: number;
  trust: number;
  last_contact_hours: number;
  tone_preference: TonePreference;
}

export type TaskStatus = "open" | "assigned" | "done" | "blocked";

export interface PendingTask {
  task_id: string;
  title: string;
  priority: number;
  deadline_hours: number;
  estimated_minutes: number;
  delegatable: boolean;
  assignee_id?: string | null;
  status: TaskStatus;
}

// ---------------------------------------------------------------------------
// Observation
// ---------------------------------------------------------------------------

export type ScenarioCategory =
  | "calendar_conflict"
  | "email_triage"
  | "message_reply"
  | "dinner_planning"
  | "delegation"
  | "shopping";

export type Difficulty = "easy" | "medium" | "hard";

export interface AriaObservation {
  // OpenEnv base fields
  done: boolean;
  reward: number;
  metadata: Record<string, unknown>;

  time: number;
  location: Location;
  calendar: CalendarEvent[];
  inbox: InboxItem[];
  relationships: RelationshipNode[];
  pending_tasks: PendingTask[];
  preferences: number[];

  scenario_category?: ScenarioCategory | null;
  difficulty?: Difficulty | null;

  step_count: number;
  max_steps: number;

  reward_breakdown?: RewardBreakdown | null;
}

// ---------------------------------------------------------------------------
// Reward
// ---------------------------------------------------------------------------

export const REWARD_WEIGHTS: Readonly<Record<RewardDimension, number>> = {
  task_completion: 0.25,
  relationship_health: 0.2,
  user_satisfaction: 0.2,
  time_efficiency: 0.15,
  conflict_resolution: 0.15,
  safety: 0.05,
};

export type RewardDimension =
  | "task_completion"
  | "relationship_health"
  | "user_satisfaction"
  | "time_efficiency"
  | "conflict_resolution"
  | "safety";

export const REWARD_DIMENSIONS: readonly RewardDimension[] = [
  "task_completion",
  "relationship_health",
  "user_satisfaction",
  "time_efficiency",
  "conflict_resolution",
  "safety",
] as const;

export interface RewardBreakdown {
  task_completion: number;
  relationship_health: number;
  user_satisfaction: number;
  time_efficiency: number;
  conflict_resolution: number;
  safety: number;
  total: number;
}

// ---------------------------------------------------------------------------
// Gateway events
// ---------------------------------------------------------------------------

export type GwEventKind =
  | "session_start"
  | "partial_transcript"
  | "final_transcript"
  | "tool_call"
  | "reply_text"
  | "tts_chunk"
  | "env_step"
  | "reward"
  | "error";

export interface GwAgentEvent {
  session_id: string;
  kind: GwEventKind;
  payload: Record<string, unknown>;
  ts_ms: number;
}

export interface GwSessionStart {
  session_id: string;
  mode: "live" | "simulated";
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export type MemoryNamespace =
  | "episodic"
  | "semantic"
  | "relationship"
  | "preference";

// ---------------------------------------------------------------------------
// Voice
// ---------------------------------------------------------------------------

export interface VoiceTranscript {
  session_id: string;
  text: string;
  is_final: boolean;
  confidence: number;
  start_ms: number;
  end_ms: number;
  lang: string;
}
