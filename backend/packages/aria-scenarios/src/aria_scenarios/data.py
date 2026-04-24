"""Seed data used across generators. Kept deliberately small and deterministic."""
from __future__ import annotations

# A small roster of named contacts with built-in relationship kinds.
CONTACTS: list[tuple[str, str, str]] = [
    # (contact_id, name, relationship_kind)
    ("c_boss",    "Priya Shah",    "boss"),
    ("c_report",  "Azim Kurien",   "report"),
    ("c_partner", "Riya",          "partner"),
    ("c_family",  "Mom",           "family"),
    ("c_friend1", "Indrajeet",     "friend"),
    ("c_friend2", "Dev",           "friend"),
    ("c_coll1",   "Anushka",       "colleague"),
    ("c_coll2",   "Rahul",         "colleague"),
    ("c_vendor",  "Flipkart",      "vendor"),
]

EMAIL_SUBJECTS: list[str] = [
    "Quick question about the deck",
    "Contract redlines attached",
    "Can we move our 5pm?",
    "Invoice #4421",
    "Thoughts on the proposal?",
    "Weekend plans?",
    "URGENT: bug in checkout",
    "Happy birthday!",
    "Your order has shipped",
    "Reminder: parent-teacher meeting",
]

EVENT_TITLES: list[str] = [
    "Team standup",
    "1:1 with Priya",
    "Design review",
    "Lunch with Riya",
    "Gym",
    "Parent-teacher meeting",
    "Quarterly review",
    "Dinner at home",
    "School play",
    "Call with vendor",
]

TASK_TITLES: list[str] = [
    "Review Q3 deck",
    "Approve design mocks",
    "Respond to vendor contract",
    "Pick up groceries",
    "Book flight for next month",
    "Send birthday card",
    "Update LinkedIn",
    "Schedule dentist",
    "Pay electricity bill",
    "Reply to Indrajeet",
]
