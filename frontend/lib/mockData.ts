/**
 * Mock data for when the gateway is unreachable.
 * One full scenario — a calendar_conflict episode on medium.
 * Events tick through on a timer so the demo is visually alive.
 */
import type {
  AriaObservation,
  GwAgentEvent,
  RewardBreakdown,
} from "./contracts";

export const MOCK_OBSERVATION: AriaObservation = {
  done: false,
  reward: null,
  metadata: { step_count: 0 },
  time: 8.25,
  location: "home",
  scenario_category: "calendar_conflict",
  difficulty: "medium",
  step_count: 0,
  max_steps: 50,
  preferences: new Array(64).fill(0).map((_, i) => Math.sin(i / 6) * 0.3),
  calendar: [
    { event_id: "evt_001", day_offset: 0, start_hour: 9.0,  end_hour: 9.5,  title: "Team standup",              priority: 0.6,  flexibility: 0.2, participant_ids: ["c_coll1"],      location: "office" },
    { event_id: "evt_002", day_offset: 0, start_hour: 11.0, end_hour: 12.0, title: "Design review",             priority: 0.7,  flexibility: 0.5, participant_ids: ["c_coll2"],      location: "office" },
    { event_id: "evt_003", day_offset: 0, start_hour: 13.0, end_hour: 13.5, title: "Lunch with Riya",           priority: 0.5,  flexibility: 0.4, participant_ids: ["c_partner"],    location: "other"  },
    { event_id: "conflict_work",     day_offset: 0, start_hour: 17.0,  end_hour: 18.0,  title: "Board review with Priya", priority: 0.9,  flexibility: 0.3, participant_ids: ["c_boss"],    location: "office" },
    { event_id: "conflict_personal", day_offset: 0, start_hour: 17.25, end_hour: 18.25, title: "Riya's school play",      priority: 0.85, flexibility: 0.1, participant_ids: ["c_partner"], location: "other"  },
    { event_id: "evt_006", day_offset: 1, start_hour: 10.0, end_hour: 11.0, title: "1:1 with Priya",            priority: 0.7,  flexibility: 0.3, participant_ids: ["c_boss"],       location: "office" },
    { event_id: "evt_007", day_offset: 2, start_hour: 15.0, end_hour: 16.0, title: "Quarterly review",          priority: 0.85, flexibility: 0.2, participant_ids: ["c_boss"],       location: "office" },
    { event_id: "evt_008", day_offset: 3, start_hour: 19.0, end_hour: 20.5, title: "Dinner at home",            priority: 0.65, flexibility: 0.5, participant_ids: ["c_partner","c_family"], location: "home" },
  ],
  inbox: [
    { email_id: "em_0001", sender_id: "c_boss",    subject: "URGENT: bug in checkout",      urgency: 0.95, age_hours: 0.5,  requires_reply: true,  sentiment: -0.2 },
    { email_id: "em_0002", sender_id: "c_partner", subject: "Are you free to talk?",        urgency: 0.88, age_hours: 1.5,  requires_reply: true,  sentiment: -0.6 },
    { email_id: "em_0003", sender_id: "c_coll1",   subject: "Contract redlines attached",   urgency: 0.72, age_hours: 3.0,  requires_reply: true,  sentiment:  0.05 },
    { email_id: "em_0004", sender_id: "c_friend1", subject: "Weekend plans?",               urgency: 0.40, age_hours: 6.0,  requires_reply: true,  sentiment:  0.3 },
    { email_id: "em_0005", sender_id: "c_vendor",  subject: "Invoice #4421",                urgency: 0.30, age_hours: 14.0, requires_reply: false, sentiment:  0.0 },
    { email_id: "em_0006", sender_id: "c_coll2",   subject: "Thoughts on the proposal?",    urgency: 0.28, age_hours: 22.0, requires_reply: true,  sentiment:  0.1 },
    { email_id: "em_0007", sender_id: "c_family",  subject: "Happy birthday!",              urgency: 0.20, age_hours: 5.0,  requires_reply: false, sentiment:  0.7 },
    { email_id: "em_0008", sender_id: "c_friend2", subject: "Quick question about the deck",urgency: 0.18, age_hours: 30.0, requires_reply: false, sentiment:  0.0 },
  ],
  relationships: [
    { contact_id: "c_boss",    name: "Priya Shah",    relationship_kind: "boss",      closeness: 0.72, trust: 0.88, last_contact_hours: 2.0,  tone_preference: "formal" },
    { contact_id: "c_report",  name: "Azim Kurien",   relationship_kind: "report",    closeness: 0.68, trust: 0.90, last_contact_hours: 18.0, tone_preference: "direct" },
    { contact_id: "c_partner", name: "Riya",          relationship_kind: "partner",   closeness: 0.95, trust: 0.98, last_contact_hours: 1.5,  tone_preference: "warm"   },
    { contact_id: "c_family",  name: "Mom",           relationship_kind: "family",    closeness: 0.90, trust: 0.95, last_contact_hours: 72.0, tone_preference: "warm"   },
    { contact_id: "c_friend1", name: "Indrajeet",     relationship_kind: "friend",    closeness: 0.82, trust: 0.85, last_contact_hours: 48.0, tone_preference: "casual" },
    { contact_id: "c_coll1",   name: "Anushka",       relationship_kind: "colleague", closeness: 0.55, trust: 0.70, last_contact_hours: 6.0,  tone_preference: "direct" },
  ],
  pending_tasks: [
    { task_id: "t_001", title: "Review Q3 deck",              priority: 0.80, deadline_hours: 6.0,  estimated_minutes: 45, delegatable: false, status: "open" },
    { task_id: "t_002", title: "Approve design mocks",        priority: 0.65, deadline_hours: 12.0, estimated_minutes: 20, delegatable: true,  status: "open" },
    { task_id: "t_003", title: "Respond to vendor contract",  priority: 0.45, deadline_hours: 36.0, estimated_minutes: 30, delegatable: true,  status: "open" },
    { task_id: "t_004", title: "Pick up groceries",           priority: 0.50, deadline_hours: 8.0,  estimated_minutes: 45, delegatable: false, status: "open" },
    { task_id: "t_005", title: "Schedule dentist",            priority: 0.30, deadline_hours: 60.0, estimated_minutes: 10, delegatable: false, status: "open" },
  ],
};

export const MOCK_REWARD_BREAKDOWN: RewardBreakdown = {
  task_completion:     0.42,
  relationship_health: 0.55,
  user_satisfaction:   0.60,
  time_efficiency:     0.38,
  conflict_resolution: 0.20,
  safety:              0.95,
  total:               0.49,
};

export const MOCK_RUNNING_TOTAL: RewardBreakdown = {
  task_completion:     1.85,
  relationship_health: 2.10,
  user_satisfaction:   2.40,
  time_efficiency:     1.20,
  conflict_resolution: 0.90,
  safety:              3.50,
  total:               1.98,
};

// Negative offsets relative to "now on the client" — `ws.ts` rebases these
// to `Date.now()` inside a mount effect. Module-level `Date.now()` here
// would produce different values on SSR vs client and break hydration.
export const MOCK_EVENTS: GwAgentEvent[] = [
  { session_id: "mock", kind: "session_start",      payload: { mode: "simulated" },                                                                            ts_ms: -8200 },
  { session_id: "mock", kind: "partial_transcript", payload: { text: "aria, my 5 pm conflicts" },                                                              ts_ms: -7600 },
  { session_id: "mock", kind: "final_transcript",   payload: { text: "aria, my 5 pm conflicts with riya's school play — fix it." },                            ts_ms: -7200 },
  { session_id: "mock", kind: "tool_call",          payload: { tool_name: "env.resolve_conflict", arguments: { target_id: "conflict_personal" } },            ts_ms: -6800 },
  { session_id: "mock", kind: "env_step",           payload: { action_id: 8, action: "RESOLVE_CONFLICT", target: "conflict_personal" },                       ts_ms: -6400 },
  { session_id: "mock", kind: "reward",             payload: { total: 0.65, breakdown: MOCK_REWARD_BREAKDOWN },                                                ts_ms: -6000 },
  { session_id: "mock", kind: "reply_text",         payload: { text: "Board review pushed to 6:15 pm. Priya notified. Riya's play protected." },              ts_ms: -5600 },
];

export const MOCK_STREAM: GwAgentEvent[] = [
  { session_id: "mock", kind: "partial_transcript", payload: { text: "reply to indrajeet" },                                                                 ts_ms: 0 },
  { session_id: "mock", kind: "final_transcript",   payload: { text: "reply to indrajeet — tell him the api is ready." },                                   ts_ms: 400 },
  { session_id: "mock", kind: "tool_call",          payload: { tool_name: "orchestrator.map_intent", arguments: { action_id: 5 } },                          ts_ms: 550 },
  { session_id: "mock", kind: "env_step",           payload: { action_id: 5, action: "DRAFT_REPLY", target: "em_0004" },                                     ts_ms: 800 },
  { session_id: "mock", kind: "reward",             payload: { total: 0.22, breakdown: { ...MOCK_REWARD_BREAKDOWN, task_completion: 0.15, user_satisfaction: 0.40, total: 0.22 } }, ts_ms: 1100 },
  { session_id: "mock", kind: "reply_text",         payload: { text: "Drafted a casual reply to Indrajeet. Preview on screen." },                            ts_ms: 1350 },
];
